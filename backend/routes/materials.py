import os
import time
from flask import Blueprint, request, jsonify, send_file, current_app
from werkzeug.utils import secure_filename
from backend.db import get_db_connection
from backend.routes.auth import get_authenticated_user_id

materials_bp = Blueprint('materials', __name__)

ALLOWED_EXTENSIONS = {'pdf', 'docx', 'ppt', 'pptx'}
MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MB

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def format_file_size(bytes_size):
    if not bytes_size or bytes_size <= 0:
        return "0 KB"
    if bytes_size < 1024 * 1024:
        return f"{bytes_size / 1024:.1f} KB"
    return f"{bytes_size / (1024 * 1024):.1f} MB"


@materials_bp.route('/api/materials', methods=['GET'])
def list_materials():
    """Retrieve all study materials uploaded by the authenticated student."""
    user_id = get_authenticated_user_id()
    if not user_id:
        return jsonify({"status": "error", "message": "Authentication required."}), 401

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT material_id, file_name, file_type, file_path, file_size, uploaded_at
            FROM materials
            WHERE user_id = %s
            ORDER BY uploaded_at DESC;
        """, (user_id,))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        materials = []
        for r in rows:
            ext = r['file_type'] or (r['file_name'].rsplit('.', 1)[1].lower() if '.' in r['file_name'] else 'pdf')
            # Extract topic name without extension
            topic_name = os.path.splitext(r['file_name'])[0].replace('_', ' ').title()
            materials.append({
                "id": str(r['material_id']),
                "name": r['file_name'],
                "type": ext.lower(),
                "topic": topic_name,
                "size": format_file_size(r['file_size']),
                "bytes": r['file_size'],
                "uploadDate": r['uploaded_at'].strftime("%b %d, %Y") if r['uploaded_at'] else "Recently"
            })

        return jsonify({
            "status": "success",
            "count": len(materials),
            "materials": materials
        }), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@materials_bp.route('/api/materials/upload', methods=['POST'])
def upload_material():
    """Upload a PDF, DOCX, or PPT/PPTX file for the authenticated student."""
    user_id = get_authenticated_user_id()
    if not user_id:
        return jsonify({"status": "error", "message": "Authentication required."}), 401

    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "No file part provided."}), 400

    file = request.files['file']
    if not file or file.filename == '':
        return jsonify({"status": "error", "message": "No file selected for upload."}), 400

    original_filename = file.filename
    if not allowed_file(original_filename):
        return jsonify({
            "status": "error",
            "message": "Unsupported file format. Please upload PDF, DOCX, or PPT/PPTX."
        }), 400

    # Read and validate length
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)

    if file_size == 0:
        return jsonify({
            "status": "error",
            "message": "Uploaded file is empty (0 bytes). Please upload a valid document."
        }), 400

    if file_size > MAX_FILE_SIZE:
        return jsonify({
            "status": "error",
            "message": f"File exceeds maximum allowed size of 25 MB ({format_file_size(file_size)})."
        }), 400

    upload_dir = current_app.config.get('UPLOAD_FOLDER') or os.path.join(current_app.root_path, 'uploads')
    os.makedirs(upload_dir, exist_ok=True)

    file_ext = original_filename.rsplit('.', 1)[1].lower()
    safe_name = secure_filename(original_filename)
    if not safe_name:
        safe_name = f"material.{file_ext}"

    unique_filename = f"user_{user_id}_{int(time.time())}_{safe_name}"
    save_path = os.path.join(upload_dir, unique_filename)

    try:
        file.save(save_path)

        # Verify the saved file exists on disk and is non-empty
        if not os.path.exists(save_path) or os.path.getsize(save_path) == 0:
            if os.path.exists(save_path):
                try: os.remove(save_path)
                except Exception: pass
            return jsonify({
                "status": "error",
                "message": "File write verification failed: saved file is empty (0 bytes)."
            }), 400

        physical_size = os.path.getsize(save_path)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO materials (user_id, file_name, file_type, file_path, file_size)
            VALUES (%s, %s, %s, %s, %s);
        """, (user_id, original_filename, file_ext, save_path, physical_size))
        conn.commit()
        mat_id = cursor.lastrowid
        cursor.close()
        conn.close()

        topic_name = os.path.splitext(original_filename)[0].replace('_', ' ').title()

        return jsonify({
            "status": "success",
            "message": f'"{original_filename}" uploaded successfully.',
            "material": {
                "id": str(mat_id),
                "material_id": mat_id,
                "name": original_filename,
                "file_name": original_filename,
                "type": file_ext,
                "topic": topic_name,
                "size": format_file_size(physical_size),
                "bytes": physical_size,
                "uploadDate": "Just now"
            }
        }), 201

    except Exception as e:
        if os.path.exists(save_path):
            try: os.remove(save_path)
            except Exception: pass
        return jsonify({"status": "error", "message": f"Upload failed: {str(e)}"}), 500


@materials_bp.route('/api/materials/<int:material_id>', methods=['DELETE'])
def delete_material(material_id):
    """Delete study material file and its database record."""
    user_id = get_authenticated_user_id()
    if not user_id:
        return jsonify({"status": "error", "message": "Authentication required."}), 401

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT file_path, file_name FROM materials WHERE material_id = %s AND user_id = %s;", (material_id, user_id))
        row = cursor.fetchone()

        if not row:
            cursor.close()
            conn.close()
            return jsonify({"status": "error", "message": "Material not found or unauthorized."}), 404

        file_path = row['file_path']
        file_name = row['file_name']

        cursor.execute("DELETE FROM materials WHERE material_id = %s AND user_id = %s;", (material_id, user_id))
        conn.commit()
        cursor.close()
        conn.close()

        # Delete physical file from disk
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as fe:
                current_app.logger.warning(f"Could not remove file {file_path}: {fe}")

        return jsonify({
            "status": "success",
            "message": f'"{file_name}" removed from library.'
        }), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@materials_bp.route('/api/materials/<int:material_id>/download', methods=['GET'])
def download_material(material_id):
    """Serve material file for viewing or download."""
    user_id = get_authenticated_user_id()
    if not user_id:
        return jsonify({"status": "error", "message": "Authentication required."}), 401

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT file_path, file_name, file_type FROM materials WHERE material_id = %s AND user_id = %s;", (material_id, user_id))
        row = cursor.fetchone()
        cursor.close()
        conn.close()

        if not row or not row['file_path'] or not os.path.exists(row['file_path']):
            return jsonify({"status": "error", "message": "File not found."}), 404

        return send_file(row['file_path'], download_name=row['file_name'], as_attachment=False)

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
