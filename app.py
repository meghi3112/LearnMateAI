import os
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

# Import database health check and connection utility
from backend.db import check_db_health, get_db_connection

# Import routes
from backend.routes.auth import auth_bp
from backend.routes.materials import materials_bp
from backend.routes.sessions import sessions_bp
from backend.routes.analytics import analytics_bp
from backend.routes.learning import learning_bp
from backend.routes.recommendations import recommendations_bp

# Load environment variables from .env file
load_dotenv()

# Initialize Flask application
app = Flask(__name__)

# Application Configuration
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY') or os.getenv('SECRET_KEY', 'learnmate_ai_default_secret_key')
upload_folder = os.getenv('UPLOAD_FOLDER', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads'))
app.config['UPLOAD_FOLDER'] = upload_folder
app.config['MAX_CONTENT_LENGTH'] = 25 * 1024 * 1024  # 25MB

# Automatically ensure upload directory exists on startup
os.makedirs(upload_folder, exist_ok=True)

# Enable Cross-Origin Resource Sharing (CORS) - configurable for deployment
cors_origins_env = os.getenv("CORS_ORIGINS", "*").strip()
allowed_origins = [o.strip() for o in cors_origins_env.split(",") if o.strip()] if cors_origins_env != "*" else "*"

CORS(app, resources={
    r"/api/*": {
        "origins": allowed_origins,
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization", "X-User-Id"]
    }
})

# Register blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(materials_bp)
app.register_blueprint(sessions_bp)
app.register_blueprint(analytics_bp)
app.register_blueprint(learning_bp)
app.register_blueprint(recommendations_bp)


# Graceful error handlers to prevent exposing sensitive stack traces
@app.errorhandler(400)
def bad_request_handler(e):
    return jsonify({"status": "error", "message": "Bad request"}), 400

@app.errorhandler(403)
def forbidden_handler(e):
    return jsonify({"status": "error", "message": "Access forbidden"}), 403

@app.errorhandler(404)
def not_found_handler(e):
    return jsonify({"status": "error", "message": "Resource not found"}), 404

@app.errorhandler(405)
def method_not_allowed_handler(e):
    return jsonify({"status": "error", "message": "Method not allowed"}), 405

@app.errorhandler(500)
def internal_error_handler(e):
    return jsonify({"status": "error", "message": "Internal server error"}), 500


@app.route('/')
def index():
    """Serve the landing page (index.html)."""
    root_dir = os.path.dirname(os.path.abspath(__file__))
    return send_from_directory(root_dir, 'index.html')


@app.route('/api/health', methods=['GET'])
def health_check():
    """
    Health check endpoint that verifies:
    - Status of the Flask server
    - Status of the MySQL database connection
    - Current database name
    - List of tables found in learnmate_ai
    """
    db_health = check_db_health()

    is_db_connected = db_health.get("status") == "connected"

    response = {
        "status": "healthy" if is_db_connected else "degraded",
        "flask_server": "running",
        "database_connection": "connected" if is_db_connected else "disconnected",
        "database_name": db_health.get("database_name"),
        "tables": db_health.get("tables", []),
        "table_count": db_health.get("table_count", 0)
    }

    if not is_db_connected:
        response["error"] = "Database connection unavailable"
        return jsonify(response), 503

    return jsonify(response), 200


@app.route('/<path:filename>')
def serve_static_file(filename):
    """
    Serve frontend static files (HTML, CSS, JS, assets) directly.
    Blocks sensitive configuration files (.env, .git, .py, etc.) from HTTP exposure.
    Supports clean URLs by resolving extensionless HTML files.
    """
    clean_name = filename.replace('\\', '/').strip('/')

    # Security check: forbid hidden files, .env, python files, backend source code, or scratch
    if (clean_name.startswith('api/') or
        clean_name == 'api' or
        clean_name.startswith('.') or
        '/.' in clean_name or
        clean_name.endswith('.env') or
        '.env.' in clean_name or
        clean_name.endswith('.py') or
        clean_name.endswith('.pyc') or
        clean_name.startswith('backend/') or
        clean_name.startswith('scratch/')):
        return jsonify({"status": "error", "message": "Access denied"}), 403

    root_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(root_dir, clean_name)

    if os.path.isfile(file_path):
        return send_from_directory(root_dir, clean_name)

    # Support clean URLs (e.g., /login -> login.html, /app -> app.html)
    if os.path.isfile(file_path + '.html'):
        return send_from_directory(root_dir, clean_name + '.html')

    return jsonify({"status": "error", "message": "File not found"}), 404


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    debug_mode = os.getenv('FLASK_DEBUG', 'true').lower() in ('true', '1', 't')
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
