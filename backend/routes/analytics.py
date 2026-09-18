from flask import Blueprint, request, jsonify
from backend.db import get_db_connection
from backend.routes.auth import get_authenticated_user_id, fetch_user_preferences

analytics_bp = Blueprint('analytics', __name__)

def get_performance_level(score):
    """
    Map percentage score to MySQL performance_level ENUM:
    < 70   -> 'needs_improvement'
    70-79  -> 'average'
    80-89  -> 'good'
    90+    -> 'excellent'
    """
    if score >= 90:
        return 'excellent'
    elif score >= 80:
        return 'good'
    elif score >= 70:
        return 'average'
    else:
        return 'needs_improvement'


@analytics_bp.route('/api/performance', methods=['GET'])
def get_performance():
    """Retrieve real performance metrics, score trends, and topic breakdown for authenticated student."""
    user_id = get_authenticated_user_id()
    if not user_id:
        return jsonify({"status": "error", "message": "Authentication required."}), 401

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Count topics studied
        cursor.execute("SELECT COUNT(DISTINCT topic) as topic_count FROM learning_sessions WHERE user_id = %s;", (user_id,))
        topic_count = cursor.fetchone()['topic_count'] or 0

        # Query quiz attempts
        cursor.execute("""
            SELECT attempt_id, score, total_questions, attempted_at
            FROM quiz_attempts
            WHERE user_id = %s
            ORDER BY attempted_at ASC;
        """, (user_id,))
        attempts = cursor.fetchall()

        # Query performance table
        cursor.execute("""
            SELECT topic, quiz_score, attempts, completion_percentage, performance_level
            FROM performance
            WHERE user_id = %s
            ORDER BY recorded_at DESC;
        """, (user_id,))
        perf_rows = cursor.fetchall()

        cursor.close()
        conn.close()

        quizzes_count = len(attempts)

        if quizzes_count == 0 and len(perf_rows) == 0:
            return jsonify({
                "status": "success",
                "has_data": False,
                "kpis": {
                    "topicsStudied": f"{topic_count} Topics" if topic_count > 0 else "0 Topics",
                    "quizzesAttempted": "0 Quizzes",
                    "averageScore": "0%",
                    "overallProgress": "0%"
                },
                "scoreTrend": [],
                "topicBreakdown": [],
                "strongTopics": [],
                "weakTopics": []
            }), 200

        # Calculate average score
        total_score = sum(float(a['score']) for a in attempts)
        avg_score = round(total_score / quizzes_count, 1) if quizzes_count > 0 else 0.0

        # Build score trend points
        score_trend = []
        for a in attempts:
            dt = a['attempted_at']
            date_label = dt.strftime("%b %d") if dt else "Recent"
            score_trend.append({
                "date": date_label,
                "score": round(float(a['score']))
            })

        # Build topic breakdown
        topic_breakdown = []
        strong_topics = []
        weak_topics = []

        for p in perf_rows:
            sc = round(float(p['quiz_score']))
            status = "strong" if sc >= 80 else ("needs-improvement" if sc < 70 else "average")
            item = {
                "topic": p['topic'],
                "score": sc,
                "attempts": p['attempts'],
                "status": status
            }
            topic_breakdown.append(item)
            if sc >= 80:
                strong_topics.append(item)
            elif sc < 70:
                weak_topics.append(item)

        return jsonify({
            "status": "success",
            "has_data": True,
            "kpis": {
                "topicsStudied": f"{topic_count} Topics",
                "quizzesAttempted": f"{quizzes_count} Quizzes",
                "averageScore": f"{avg_score}%",
                "overallProgress": f"{round(avg_score)}%"
            },
            "scoreTrend": score_trend,
            "topicBreakdown": topic_breakdown,
            "strongTopics": strong_topics,
            "weakTopics": weak_topics
        }), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@analytics_bp.route('/api/performance/quiz-attempt', methods=['POST'])
def record_quiz_attempt():
    """Record a real quiz attempt and update student performance in MySQL."""
    user_id = get_authenticated_user_id()
    if not user_id:
        return jsonify({"status": "error", "message": "Authentication required."}), 401

    data = request.get_json() or {}
    topic = (data.get('topic') or '').strip()
    score = float(data.get('score', 0))
    total_questions = int(data.get('total_questions', 10))
    session_id = data.get('session_id')

    if not topic:
        return jsonify({"status": "error", "message": "Topic is required."}), 400

    attempt_level = get_performance_level(score)

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # If session_id provided, verify or create quiz
        quiz_id = None
        if session_id:
            cursor.execute("SELECT quiz_id FROM quizzes WHERE session_id = %s LIMIT 1;", (session_id,))
            q_row = cursor.fetchone()
            if q_row:
                quiz_id = q_row[0]
            else:
                cursor.execute("""
                    INSERT INTO quizzes (session_id, difficulty, total_questions)
                    VALUES (%s, 'medium', %s);
                """, (session_id, total_questions))
                quiz_id = cursor.lastrowid
        else:
            # Create a detached quiz record if no session_id provided
            cursor.execute("SELECT session_id FROM learning_sessions WHERE user_id = %s AND topic = %s ORDER BY session_id DESC LIMIT 1;", (user_id, topic))
            s_row = cursor.fetchone()
            if s_row:
                session_id = s_row[0]
                cursor.execute("INSERT INTO quizzes (session_id, difficulty, total_questions) VALUES (%s, 'medium', %s);", (session_id, total_questions))
                quiz_id = cursor.lastrowid
            else:
                # Create a session for this topic
                cursor.execute("INSERT INTO learning_sessions (user_id, topic, source_type) VALUES (%s, %s, 'topic');", (user_id, topic))
                session_id = cursor.lastrowid
                cursor.execute("INSERT INTO quizzes (session_id, difficulty, total_questions) VALUES (%s, 'medium', %s);", (session_id, total_questions))
                quiz_id = cursor.lastrowid

        # Insert attempt
        cursor.execute("""
            INSERT INTO quiz_attempts (quiz_id, user_id, score, total_questions)
            VALUES (%s, %s, %s, %s);
        """, (quiz_id, user_id, score, total_questions))

        # Update or insert performance
        cursor.execute("SELECT performance_id, attempts, quiz_score FROM performance WHERE user_id = %s AND topic = %s LIMIT 1;", (user_id, topic))
        perf_row = cursor.fetchone()
        if perf_row:
            p_id, old_attempts, old_score = perf_row
            new_attempts = (old_attempts or 0) + 1
            new_avg = round((float(old_score) * old_attempts + score) / new_attempts, 2)
            overall_level = get_performance_level(new_avg)
            cursor.execute("""
                UPDATE performance
                SET quiz_score = %s, attempts = %s, completion_percentage = 100.0, performance_level = %s, session_id = %s, recorded_at = CURRENT_TIMESTAMP
                WHERE performance_id = %s;
            """, (new_avg, new_attempts, overall_level, session_id, p_id))
        else:
            overall_level = attempt_level
            cursor.execute("""
                INSERT INTO performance (user_id, session_id, topic, quiz_score, attempts, completion_percentage, performance_level)
                VALUES (%s, %s, %s, %s, 1, 100.0, %s);
            """, (user_id, session_id, topic, score, overall_level))

        conn.commit()
        cursor.close()
        conn.close()

        # Dynamically recalculate adaptive recommendations for student
        try:
            RecommendationService.generate_recommendations_for_user(user_id)
        except Exception as rec_err:
            pass

        return jsonify({
            "status": "success",
            "message": "Quiz attempt recorded successfully.",
            "score": score,
            "performance_level": overall_level,
            "attempt_level": attempt_level
        }), 201

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


from backend.services.recommendation_service import RecommendationService


@analytics_bp.route('/api/recommendations', methods=['GET'])
def get_recommendations():
    """Retrieve personalized recommendations based on real student performance, history, and preferences."""
    user_id = get_authenticated_user_id()
    if not user_id:
        return jsonify({"status": "error", "message": "Authentication required."}), 401

    try:
        result = RecommendationService.generate_recommendations_for_user(user_id)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

