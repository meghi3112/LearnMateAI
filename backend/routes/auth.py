import re
from flask import Blueprint, request, jsonify, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from backend.db import get_db_connection

auth_bp = Blueprint('auth', __name__)

PREFERENCE_MAP = {
    "simple_concise": ["simple & concise", "simple_concise", "simple"],
    "detailed": ["detailed"],
    "step_by_step": ["step-by-step", "step_by_step", "step by step"],
    "visual": ["visual", "visual learning"],
    "practice": ["practice", "practice & quizzes", "quiz"],
    "revision": ["revision"]
}

def get_serializer():
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'])

def generate_token(user_id, email):
    s = get_serializer()
    return s.dumps({'user_id': user_id, 'email': email})

def verify_token(token):
    s = get_serializer()
    try:
        # Valid for 30 days
        data = s.loads(token, max_age=30 * 24 * 3600)
        return data
    except (BadSignature, SignatureExpired):
        return None

def get_authenticated_user_id():
    """Extract and verify user_id from Authorization header, X-User-Id, or query params."""
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        token = auth_header[7:].strip()
        data = verify_token(token)
        if data:
            return data.get('user_id')
    
    # Fallback to X-User-Id header if token not provided
    user_id_header = request.headers.get('X-User-Id')
    if user_id_header and user_id_header.isdigit():
        return int(user_id_header)

    # Fallback to token query parameter (essential for file download and window.open)
    token_param = request.args.get('token')
    if token_param:
        data = verify_token(token_param)
        if data:
            return data.get('user_id')

    # Fallback to user_id query parameter
    uid_param = request.args.get('user_id')
    if uid_param and uid_param.isdigit():
        return int(uid_param)
    
    return None

def fetch_user_preferences(cursor, user_id):
    """Retrieve formatted preferences list for a user."""
    cursor.execute("""
        SELECT simple_concise, detailed, step_by_step, visual, practice, revision
        FROM learning_preferences
        WHERE user_id = %s
        ORDER BY preference_id DESC
        LIMIT 1;
    """, (user_id,))
    pref_row = cursor.fetchone()
    
    prefs = []
    if pref_row:
        if isinstance(pref_row, dict):
            if pref_row.get("simple_concise"): prefs.append("Simple & Concise")
            if pref_row.get("detailed"): prefs.append("Detailed")
            if pref_row.get("step_by_step"): prefs.append("Step-by-Step")
            if pref_row.get("visual"): prefs.append("Visual")
            if pref_row.get("practice"): prefs.append("Practice")
            if pref_row.get("revision"): prefs.append("Revision")
        else:
            if pref_row[0]: prefs.append("Simple & Concise")
            if pref_row[1]: prefs.append("Detailed")
            if pref_row[2]: prefs.append("Step-by-Step")
            if pref_row[3]: prefs.append("Visual")
            if pref_row[4]: prefs.append("Practice")
            if pref_row[5]: prefs.append("Revision")
    
    return prefs

@auth_bp.route('/api/auth/register', methods=['POST'])
def register():
    """
    Register a new student account.
    Stores full_name, email, Werkzeug hashed password, and initializes learning preferences.
    """
    data = request.get_json() or {}
    full_name = (data.get('full_name') or '').strip()
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''

    # Validations
    if not full_name or not email or not password:
        return jsonify({"status": "error", "message": "Full name, email, and password are required."}), 400

    email_regex = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    if not re.match(email_regex, email):
        return jsonify({"status": "error", "message": "Invalid email format."}), 400

    if len(password) < 6:
        return jsonify({"status": "error", "message": "Password must be at least 6 characters long."}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check for existing email
        cursor.execute("SELECT user_id FROM users WHERE email = %s;", (email,))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({"status": "error", "message": "An account with this email already exists."}), 409

        # Hash password and insert user
        pwd_hash = generate_password_hash(password)
        cursor.execute("""
            INSERT INTO users (full_name, email, password_hash)
            VALUES (%s, %s, %s);
        """, (full_name, email, pwd_hash))
        conn.commit()
        user_id = cursor.lastrowid

        # Initialize default learning preferences (Visual & Step-by-Step by default)
        cursor.execute("""
            INSERT INTO learning_preferences 
            (user_id, simple_concise, detailed, step_by_step, visual, practice, revision)
            VALUES (%s, 1, 0, 1, 1, 1, 0);
        """, (user_id,))
        conn.commit()

        cursor.close()
        conn.close()

        token = generate_token(user_id, email)
        initials = "".join([part[0] for part in full_name.split() if part])[:2].upper() or "ST"

        return jsonify({
            "status": "success",
            "message": "Account created successfully.",
            "token": token,
            "user": {
                "user_id": user_id,
                "full_name": full_name,
                "email": email,
                "avatar_initial": initials,
                "preferences": ["Simple & Concise", "Step-by-Step", "Visual", "Practice"]
            }
        }), 201

    except Exception as e:
        return jsonify({"status": "error", "message": f"Database error: {str(e)}"}), 500


@auth_bp.route('/api/auth/login', methods=['POST'])
def login():
    """
    Authenticate an existing student.
    Validates email and Werkzeug password hash, returning user details and token.
    """
    data = request.get_json() or {}
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''

    if not email or not password:
        return jsonify({"status": "error", "message": "Email and password are required."}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT user_id, full_name, email, password_hash, profile_picture
            FROM users 
            WHERE email = %s
            LIMIT 1;
        """, (email,))
        user_row = cursor.fetchone()

        if not user_row:
            cursor.close()
            conn.close()
            return jsonify({"status": "error", "message": "Invalid email or password."}), 401

        user_id, full_name, user_email, pwd_hash, profile_pic = user_row

        if not check_password_hash(pwd_hash, password):
            cursor.close()
            conn.close()
            return jsonify({"status": "error", "message": "Invalid email or password."}), 401

        # Fetch preferences
        preferences = fetch_user_preferences(cursor, user_id)

        cursor.close()
        conn.close()

        token = generate_token(user_id, user_email)
        initials = "".join([part[0] for part in full_name.split() if part])[:2].upper() or "ST"
        primary_focus = preferences[0] if preferences else "Visual"

        return jsonify({
            "status": "success",
            "message": "Login successful.",
            "token": token,
            "user": {
                "user_id": user_id,
                "full_name": full_name,
                "email": user_email,
                "avatar_initial": initials,
                "profile_picture": profile_pic,
                "preferences": preferences,
                "primary_focus": primary_focus
            }
        }), 200

    except Exception as e:
        return jsonify({"status": "error", "message": f"Database error: {str(e)}"}), 500


@auth_bp.route('/api/auth/me', methods=['GET'])
def get_current_user():
    """Get profile and preferences for current logged in user."""
    user_id = get_authenticated_user_id()
    if not user_id:
        return jsonify({"status": "error", "message": "Authentication required."}), 401

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT user_id, full_name, email, profile_picture, created_at
            FROM users 
            WHERE user_id = %s
            LIMIT 1;
        """, (user_id,))
        user_row = cursor.fetchone()

        if not user_row:
            cursor.close()
            conn.close()
            return jsonify({"status": "error", "message": "User not found."}), 404

        uid, full_name, email, profile_pic, created_at = user_row
        preferences = fetch_user_preferences(cursor, user_id)

        # Retrieve user activity stats
        cursor.execute("SELECT COUNT(*) FROM learning_sessions WHERE user_id = %s;", (user_id,))
        sessions_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM materials WHERE user_id = %s;", (user_id,))
        materials_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*), COALESCE(AVG(score), 0) FROM quiz_attempts WHERE user_id = %s;", (user_id,))
        stats_row = cursor.fetchone()
        quizzes_count = stats_row[0] if stats_row else 0
        avg_score = float(stats_row[1]) if stats_row else 0.0

        cursor.close()
        conn.close()

        initials = "".join([part[0] for part in full_name.split() if part])[:2].upper() or "ST"

        return jsonify({
            "status": "success",
            "user": {
                "user_id": uid,
                "full_name": full_name,
                "email": email,
                "avatar_initial": initials,
                "profile_picture": profile_pic,
                "created_at": created_at.isoformat() if created_at else None,
                "preferences": preferences,
                "primary_focus": preferences[0] if preferences else "Visual",
                "stats": {
                    "sessions_count": sessions_count,
                    "materials_count": materials_count,
                    "quizzes_count": quizzes_count,
                    "average_score": f"{avg_score:.1f}%" if quizzes_count > 0 else "0.0%"
                }
            }
        }), 200

    except Exception as e:
        return jsonify({"status": "error", "message": f"Database error: {str(e)}"}), 500


@auth_bp.route('/api/auth/profile', methods=['PUT'])
def update_profile():
    """Update profile information for the authenticated student."""
    user_id = get_authenticated_user_id()
    if not user_id:
        return jsonify({"status": "error", "message": "Authentication required."}), 401

    data = request.get_json() or {}
    full_name = (data.get('full_name') or '').strip()

    if not full_name:
        return jsonify({"status": "error", "message": "Full name cannot be empty."}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE users
            SET full_name = %s
            WHERE user_id = %s;
        """, (full_name, user_id))
        conn.commit()

        cursor.execute("SELECT user_id, full_name, email, profile_picture FROM users WHERE user_id = %s;", (user_id,))
        user_row = cursor.fetchone()
        preferences = fetch_user_preferences(cursor, user_id)
        cursor.close()
        conn.close()

        uid, name, email, pic = user_row
        initials = "".join([part[0] for part in name.split() if part])[:2].upper() or "ST"

        return jsonify({
            "status": "success",
            "message": "Profile updated successfully.",
            "user": {
                "user_id": uid,
                "full_name": name,
                "email": email,
                "avatar_initial": initials,
                "profile_picture": pic,
                "preferences": preferences,
                "primary_focus": preferences[0] if preferences else "Visual"
            }
        }), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@auth_bp.route('/api/auth/password', methods=['PUT'])
def change_password():
    """Change password for authenticated student with current password verification."""
    user_id = get_authenticated_user_id()
    if not user_id:
        return jsonify({"status": "error", "message": "Authentication required."}), 401

    data = request.get_json() or {}
    current_password = data.get('current_password') or ''
    new_password = data.get('new_password') or ''

    if not current_password or not new_password:
        return jsonify({"status": "error", "message": "Current password and new password are required."}), 400

    if len(new_password) < 6:
        return jsonify({"status": "error", "message": "New password must be at least 6 characters."}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT password_hash FROM users WHERE user_id = %s;", (user_id,))
        row = cursor.fetchone()

        if not row or not check_password_hash(row[0], current_password):
            cursor.close()
            conn.close()
            return jsonify({"status": "error", "message": "Incorrect current password."}), 401

        new_hash = generate_password_hash(new_password)
        cursor.execute("UPDATE users SET password_hash = %s WHERE user_id = %s;", (new_hash, user_id))
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"status": "success", "message": "Password changed successfully."}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@auth_bp.route('/api/auth/account', methods=['DELETE'])
def delete_account():
    """Delete authenticated student account and all cascading data."""
    user_id = get_authenticated_user_id()
    if not user_id:
        return jsonify({"status": "error", "message": "Authentication required."}), 401

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE user_id = %s;", (user_id,))
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"status": "success", "message": "Account deleted successfully."}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@auth_bp.route('/api/auth/logout', methods=['POST'])
def logout():
    """Log out current user."""
    return jsonify({"status": "success", "message": "Logged out successfully."}), 200


@auth_bp.route('/api/preferences', methods=['GET', 'POST'])
def handle_preferences():
    """
    GET: Retrieve preferences for authenticated user (or user_id query).
    POST: Update preferences for authenticated user (or user_id body).
    """
    user_id = get_authenticated_user_id()
    
    if request.method == 'GET':
        query_uid = request.args.get('user_id')
        target_uid = int(query_uid) if query_uid and query_uid.isdigit() else user_id
        if not target_uid:
            return jsonify({"status": "error", "message": "User ID is required."}), 400

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            prefs = fetch_user_preferences(cursor, target_uid)
            cursor.close()
            conn.close()

            return jsonify({
                "status": "success",
                "user_id": target_uid,
                "preferences": prefs,
                "primary_focus": prefs[0] if prefs else "Visual"
            }), 200
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    # POST: Update preferences
    data = request.get_json() or {}
    body_uid = data.get('user_id')
    target_uid = int(body_uid) if body_uid and str(body_uid).isdigit() else user_id
    if not target_uid:
        return jsonify({"status": "error", "message": "User ID is required."}), 400

    selected_prefs = data.get('preferences') or []
    # Normalize selected preferences to lower case
    selected_lower = [p.lower().strip() for p in selected_prefs]

    def is_selected(key):
        aliases = PREFERENCE_MAP[key]
        return 1 if any(alias in selected_lower for alias in aliases) else 0

    sc = is_selected('simple_concise')
    dt = is_selected('detailed')
    sb = is_selected('step_by_step')
    vs = is_selected('visual')
    pr = is_selected('practice')
    rv = is_selected('revision')

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT preference_id FROM learning_preferences WHERE user_id = %s ORDER BY preference_id DESC LIMIT 1;", (target_uid,))
        existing = cursor.fetchone()
        if existing:
            cursor.execute("""
                UPDATE learning_preferences
                SET simple_concise = %s, detailed = %s, step_by_step = %s, visual = %s, practice = %s, revision = %s
                WHERE preference_id = %s;
            """, (sc, dt, sb, vs, pr, rv, existing[0]))
        else:
            cursor.execute("""
                INSERT INTO learning_preferences 
                (user_id, simple_concise, detailed, step_by_step, visual, practice, revision)
                VALUES (%s, %s, %s, %s, %s, %s, %s);
            """, (target_uid, sc, dt, sb, vs, pr, rv))
        conn.commit()

        updated_prefs = fetch_user_preferences(cursor, target_uid)
        cursor.close()
        conn.close()

        return jsonify({
            "status": "success",
            "message": "Learning preferences saved successfully.",
            "user_id": target_uid,
            "preferences": updated_prefs,
            "primary_focus": data.get('primary_focus') or (updated_prefs[0] if updated_prefs else "Visual")
        }), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
