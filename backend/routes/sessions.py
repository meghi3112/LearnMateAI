from flask import Blueprint, request, jsonify
from backend.db import get_db_connection
from backend.routes.auth import get_authenticated_user_id

sessions_bp = Blueprint('sessions', __name__)

DEFAULT_RESOURCES = [
    "Simplified Notes",
    "Detailed Explanation",
    "Step-by-Step",
    "Summary",
    "Flashcards",
    "Q&A",
    "Diagram",
    "Quiz"
]

@sessions_bp.route('/api/sessions', methods=['GET'])
def list_sessions():
    """Retrieve all learning sessions for the authenticated student."""
    user_id = get_authenticated_user_id()
    if not user_id:
        return jsonify({"status": "error", "message": "Authentication required."}), 401

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT 
                s.session_id,
                s.topic,
                s.source_type,
                s.material_id,
                s.started_at,
                s.completed_at,
                m.file_name as material_name,
                COALESCE(MAX(qa.score), MAX(p.quiz_score)) as score
            FROM learning_sessions s
            LEFT JOIN materials m ON s.material_id = m.material_id
            LEFT JOIN quizzes q ON s.session_id = q.session_id
            LEFT JOIN quiz_attempts qa ON q.quiz_id = qa.quiz_id
            LEFT JOIN performance p ON s.session_id = p.session_id
            WHERE s.user_id = %s
            GROUP BY s.session_id, s.topic, s.source_type, s.material_id, s.started_at, s.completed_at, m.file_name
            ORDER BY s.started_at DESC;
        """, (user_id,))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        sessions = []
        for r in rows:
            started = r['started_at']
            date_str = started.strftime("%b %d, %Y") if started else "Recent"
            time_str = started.strftime("%I:%M %p") if started else "10:00 AM"

            score_val = r['score']
            if score_val is not None:
                score_display = f"{float(score_val):.0f}%"
                score_status = "success" if float(score_val) >= 80 else ("warning" if float(score_val) < 70 else "info")
            else:
                score_display = "In Progress"
                score_status = "info"

            sessions.append({
                "id": str(r['session_id']),
                "topic": r['topic'],
                "sourceType": r['source_type'] or "topic",
                "materialName": r['material_name'],
                "date": date_str,
                "time": time_str,
                "score": score_display,
                "scoreStatus": score_status,
                "resources": DEFAULT_RESOURCES
            })

        return jsonify({
            "status": "success",
            "count": len(sessions),
            "sessions": sessions
        }), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@sessions_bp.route('/api/sessions', methods=['POST'])
def create_session():
    """Create a new learning session for a topic or study material."""
    user_id = get_authenticated_user_id()
    if not user_id:
        return jsonify({"status": "error", "message": "Authentication required."}), 401

    data = request.get_json() or {}
    topic = (data.get('topic') or '').strip()
    source_type = data.get('source_type') or 'topic'
    material_id = data.get('material_id')

    if not topic:
        return jsonify({"status": "error", "message": "Topic is required."}), 400

    if source_type not in ('topic', 'material'):
        source_type = 'topic'

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO learning_sessions (user_id, topic, source_type, material_id)
            VALUES (%s, %s, %s, %s);
        """, (user_id, topic, source_type, material_id))
        conn.commit()
        session_id = cursor.lastrowid
        cursor.close()
        conn.close()

        return jsonify({
            "status": "success",
            "message": "Learning session started.",
            "session": {
                "id": str(session_id),
                "topic": topic,
                "sourceType": source_type,
                "material_id": material_id,
                "resources": DEFAULT_RESOURCES
            }
        }), 201

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@sessions_bp.route('/api/sessions/<int:session_id>', methods=['DELETE'])
def delete_session(session_id):
    """Delete a learning session for the authenticated student."""
    user_id = get_authenticated_user_id()
    if not user_id:
        return jsonify({"status": "error", "message": "Authentication required."}), 401

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM learning_sessions WHERE session_id = %s AND user_id = %s;", (session_id, user_id))
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({
            "status": "success",
            "message": "Learning session deleted from history."
        }), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
