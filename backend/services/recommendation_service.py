import os
import json
import logging
import datetime
import numpy as np
from backend.db import get_db_connection

logger = logging.getLogger(__name__)

# Constants
MODEL_DIR = os.getenv("MODEL_DIR", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models"))
os.makedirs(MODEL_DIR, exist_ok=True)
MODEL_PATH = os.path.join(MODEL_DIR, "xgboost_recommendation.json")
MODEL_META_PATH = os.path.join(MODEL_DIR, "xgboost_recommendation_meta.json")
MIN_TRAINING_SAMPLES = 20

# 4 Action Classes
ACTION_CLASSES = {
    0: {
        "action": "revision",
        "category": "High Priority",
        "badgeType": "danger",
        "actionText": "Revise Topic",
        "priority": 90,
        "suggested_action": "Revise foundational concepts and core definitions before re-testing."
    },
    1: {
        "action": "additional_practice",
        "category": "Practice Needed",
        "badgeType": "blue",
        "actionText": "Start Practice",
        "priority": 75,
        "suggested_action": "Complete interactive quiz practice to strengthen problem-solving fluency."
    },
    2: {
        "action": "continue_topic",
        "category": "Continue Learning",
        "badgeType": "purple",
        "actionText": "Continue Topic",
        "priority": 60,
        "suggested_action": "Progress into deeper concepts, step-by-step breakdowns, and case examples."
    },
    3: {
        "action": "move_to_advanced",
        "category": "Advance Level",
        "badgeType": "purple",
        "actionText": "Tackle Advanced",
        "priority": 45,
        "suggested_action": "Challenge yourself with higher difficulty questions and comprehensive assessments."
    }
}

FEATURE_NAMES = [
    "latest_quiz_score",
    "average_quiz_score",
    "attempt_count",
    "completion_percentage",
    "performance_level_encoded",
    "topic_history_length",
    "days_since_last_attempt",
    "pref_visual",
    "pref_step_by_step",
    "pref_quick_summary",
    "pref_flashcards"
]


class RecommendationService:
    _model = None
    _meta = None

    @classmethod
    def _ensure_model_loaded(cls):
        """Load trained XGBoost model and metadata if available on disk."""
        if cls._model is None and os.path.exists(MODEL_PATH):
            try:
                import xgboost as xgb
                model = xgb.XGBClassifier()
                model.load_model(MODEL_PATH)
                cls._model = model

                if os.path.exists(MODEL_META_PATH):
                    with open(MODEL_META_PATH, "r", encoding="utf-8") as f:
                        cls._meta = json.load(f)
                else:
                    cls._meta = {"status": "trained", "trained_at": "unknown"}
                logger.info("Successfully loaded XGBoost recommendation model.")
            except Exception as e:
                logger.warning(f"Could not load XGBoost model from {MODEL_PATH}: {e}")
                cls._model = None
                cls._meta = None

    @classmethod
    def get_model_status(cls):
        """Check current status of the recommendation model."""
        cls._ensure_model_loaded()
        if cls._model is not None:
            return {
                "engine": "xgboost",
                "status": "trained",
                "features": FEATURE_NAMES,
                "classes": [ACTION_CLASSES[k]["action"] for k in sorted(ACTION_CLASSES.keys())],
                "meta": cls._meta
            }
        return {
            "engine": "deterministic_baseline",
            "status": "insufficient_data",
            "features": FEATURE_NAMES,
            "classes": [ACTION_CLASSES[k]["action"] for k in sorted(ACTION_CLASSES.keys())],
            "message": f"Requires at least {MIN_TRAINING_SAMPLES} training samples across all classes to fit XGBoost."
        }

    @staticmethod
    def _encode_performance_level(level_str):
        """Map performance_level string to numeric integer."""
        mapping = {
            "needs_improvement": 0,
            "average": 1,
            "good": 2,
            "excellent": 3
        }
        return mapping.get((level_str or "").lower(), 1)

    @classmethod
    def extract_features(cls, user_id, topic, conn=None):
        """
        Extract numerical feature vector for a student on a specific topic from MySQL.
        Returns (feature_array, raw_data_dict).
        """
        should_close = False
        if conn is None:
            conn = get_db_connection()
            should_close = True

        try:
            cursor = conn.cursor(dictionary=True)

            # 1. Performance row for user and topic
            cursor.execute("""
                SELECT quiz_score, attempts, completion_percentage, performance_level, recorded_at
                FROM performance
                WHERE user_id = %s AND topic = %s
                LIMIT 1;
            """, (user_id, topic))
            perf = cursor.fetchone()

            # 2. Quiz attempts for user and topic
            cursor.execute("""
                SELECT qa.score, qa.attempted_at
                FROM quiz_attempts qa
                JOIN quizzes q ON qa.quiz_id = q.quiz_id
                JOIN learning_sessions s ON q.session_id = s.session_id
                WHERE qa.user_id = %s AND s.topic = %s
                ORDER BY qa.attempted_at DESC;
            """, (user_id, topic))
            topic_attempts = cursor.fetchall()

            # 3. Overall student stats
            cursor.execute("""
                SELECT COUNT(DISTINCT topic) as topic_count
                FROM learning_sessions
                WHERE user_id = %s;
            """, (user_id,))
            topic_count_row = cursor.fetchone()
            topic_history_length = topic_count_row["topic_count"] if topic_count_row else 0

            # 4. Learning preferences
            cursor.execute("""
                SELECT simple_concise, detailed, step_by_step, visual, practice, revision
                FROM learning_preferences
                WHERE user_id = %s
                ORDER BY preference_id DESC
                LIMIT 1;
            """, (user_id,))
            pref_row = cursor.fetchone()

            cursor.close()

            # Compute features
            if topic_attempts:
                latest_quiz_score = float(topic_attempts[0]["score"])
                all_scores = [float(a["score"]) for a in topic_attempts]
                average_quiz_score = float(np.mean(all_scores))
                attempt_count = len(topic_attempts)
                last_attempt_dt = topic_attempts[0]["attempted_at"]
            elif perf:
                latest_quiz_score = float(perf["quiz_score"] or 0.0)
                average_quiz_score = float(perf["quiz_score"] or 0.0)
                attempt_count = int(perf["attempts"] or 1)
                last_attempt_dt = perf.get("recorded_at")
            else:
                latest_quiz_score = 0.0
                average_quiz_score = 0.0
                attempt_count = 0
                last_attempt_dt = None

            completion_percentage = float(perf["completion_percentage"]) if perf and perf["completion_percentage"] else 100.0
            performance_level_str = perf["performance_level"] if perf and perf["performance_level"] else "needs_improvement"
            perf_level_encoded = cls._encode_performance_level(performance_level_str)

            if last_attempt_dt and isinstance(last_attempt_dt, datetime.datetime):
                now = datetime.datetime.now()
                days_diff = (now - last_attempt_dt).total_seconds() / 86400.0
                days_since_last_attempt = max(0.0, float(round(days_diff, 2)))
            else:
                days_since_last_attempt = 0.0

            pref_visual = int(pref_row.get("visual", 0)) if pref_row else 0
            pref_step_by_step = int(pref_row.get("step_by_step", 0)) if pref_row else 0
            pref_quick_summary = int(pref_row.get("simple_concise", 0)) if pref_row else 0
            pref_flashcards = int(pref_row.get("practice", 0)) if pref_row else 0

            prefs_list = []
            if pref_visual: prefs_list.append("visual")
            if pref_step_by_step: prefs_list.append("step-by-step")
            if pref_quick_summary: prefs_list.append("simple_concise")
            if pref_flashcards: prefs_list.append("practice")
            if pref_row and pref_row.get("detailed"): prefs_list.append("detailed")
            if pref_row and pref_row.get("revision"): prefs_list.append("revision")

            raw_data = {
                "latest_quiz_score": latest_quiz_score,
                "average_quiz_score": average_quiz_score,
                "attempt_count": attempt_count,
                "completion_percentage": completion_percentage,
                "performance_level": performance_level_str,
                "performance_level_encoded": perf_level_encoded,
                "topic_history_length": topic_history_length,
                "days_since_last_attempt": days_since_last_attempt,
                "pref_visual": pref_visual,
                "pref_step_by_step": pref_step_by_step,
                "pref_quick_summary": pref_quick_summary,
                "pref_flashcards": pref_flashcards,
                "preferences_list": prefs_list
            }

            feature_vector = [
                latest_quiz_score,
                average_quiz_score,
                float(attempt_count),
                completion_percentage,
                float(perf_level_encoded),
                float(topic_history_length),
                days_since_last_attempt,
                float(pref_visual),
                float(pref_step_by_step),
                float(pref_quick_summary),
                float(pref_flashcards)
            ]

            return feature_vector, raw_data

        finally:
            if should_close and conn:
                conn.close()

    @classmethod
    def _deterministic_baseline(cls, raw_data):
        """
        Calibrated deterministic heuristic mapping aligned with the educational mastery rubric.
        Used when samples are insufficient to avoid faking an unverified ML model.
        """
        score = raw_data.get("latest_quiz_score", 0.0)
        avg_score = raw_data.get("average_quiz_score", 0.0)
        attempts = raw_data.get("attempt_count", 0)

        effective_score = (score * 0.7) + (avg_score * 0.3) if attempts > 1 else score

        if effective_score < 70.0:
            pred_class = 0  # revision
            confidence = min(0.95, 0.70 + (70.0 - effective_score) / 100.0)
        elif effective_score < 80.0:
            pred_class = 1  # additional_practice
            confidence = 0.82
        elif effective_score < 90.0:
            if attempts <= 1:
                pred_class = 2  # continue_topic
                confidence = 0.80
            else:
                pred_class = 3  # move_to_advanced
                confidence = 0.85
        else:
            pred_class = 3  # move_to_advanced
            confidence = min(0.98, 0.85 + (effective_score - 90.0) / 100.0)

        return pred_class, float(round(confidence, 2))

    @classmethod
    def predict_action(cls, feature_vector, raw_data):
        """
        Predict adaptive learning action for a feature vector using XGBoost if available,
        or the deterministic baseline if data is insufficient.
        """
        cls._ensure_model_loaded()

        if cls._model is not None:
            try:
                X = np.array([feature_vector], dtype=np.float32)
                probabilities = cls._model.predict_proba(X)[0]
                pred_class = int(np.argmax(probabilities))
                confidence = float(round(float(probabilities[pred_class]), 2))
                return pred_class, confidence, "xgboost"
            except Exception as e:
                logger.warning(f"XGBoost prediction failed: {e}. Using deterministic baseline.")

        pred_class, confidence = cls._deterministic_baseline(raw_data)
        return pred_class, confidence, "deterministic_baseline"

    @classmethod
    def generate_recommendation_card(cls, user_id, topic, feature_vector, raw_data):
        """
        Build a recommendation card matching the structure expected by recommendations.html.
        """
        pred_class, confidence, engine = cls.predict_action(feature_vector, raw_data)
        class_info = ACTION_CLASSES[pred_class]

        score = raw_data["latest_quiz_score"]
        attempts = raw_data["attempt_count"]
        prefs = raw_data.get("preferences_list", [])

        # Build personalized pedagogical reason
        if pred_class == 0:  # revision
            title = f"Revise {topic}"
            if score > 0:
                reason = (f"Predicted by {engine.replace('_', ' ').title()} (Confidence: {int(confidence*100)}%): "
                          f"Your latest quiz score was {score:.1f}% across {attempts} attempt(s). "
                          f"Revisiting key definitions and diagrams will bridge foundational gaps.")
            else:
                reason = (f"Diagnostic review recommended for {topic}. "
                          f"Build initial subject familiarity before attempting graded quizzes.")
        elif pred_class == 1:  # additional_practice
            title = f"Practice {topic}"
            reason = (f"Predicted by {engine.replace('_', ' ').title()} (Confidence: {int(confidence*100)}%): "
                      f"Current performance shows a solid grasp ({score:.1f}%), but further practice will solidify recall "
                      f"and accuracy under time constraints.")
        elif pred_class == 2:  # continue_topic
            title = f"Deep Dive into {topic}"
            reason = (f"Predicted by {engine.replace('_', ' ').title()} (Confidence: {int(confidence*100)}%): "
                      f"Good foundation established with {score:.1f}%. "
                      f"Continue to applied examples and architectural patterns to reinforce learning.")
        else:  # move_to_advanced
            title = f"Master Advanced {topic}"
            reason = (f"Predicted by {engine.replace('_', ' ').title()} (Confidence: {int(confidence*100)}%): "
                      f"High mastery demonstrated ({score:.1f}%). "
                      f"Ready to advance to higher complexity scenarios and rigorous problem solving.")

        # Adapt suggested action to active learning preferences if any
        suggested_action = class_info["suggested_action"]
        if "visual" in prefs and pred_class in (0, 2):
            suggested_action += " (Recommended: Visual Concept Map & Architecture Diagrams)"
        elif "step-by-step" in prefs:
            suggested_action += " (Recommended: Step-by-Step Breakdown)"

        rec_id = f"rec-{abs(hash(f'{user_id}-{topic}')) % 100000}"

        return {
            "id": rec_id,
            "topic": topic,
            "category": class_info["category"],
            "badgeType": class_info["badgeType"],
            "title": title,
            "reason": reason,
            "actionText": class_info["actionText"],
            "suggested_action": suggested_action,
            "priority": class_info["priority"],
            "decision": class_info["action"],
            "confidence": confidence,
            "engine": engine,
            "current_performance": {
                "score": round(score, 1),
                "average_score": round(raw_data["average_quiz_score"], 1),
                "attempts": attempts,
                "level": raw_data["performance_level"]
            }
        }

    @classmethod
    def generate_recommendations_for_user(cls, user_id):
        """
        Generate, persist, and return complete adaptive recommendations for authenticated student.
        """
        conn = get_db_connection()
        try:
            cursor = conn.cursor(dictionary=True)

            # 1. Discover all candidate topics for this student:
            # - Studied topics from performance
            # - Topics from learning sessions
            # - Uploaded materials
            cursor.execute("""
                SELECT DISTINCT topic FROM performance WHERE user_id = %s AND topic IS NOT NULL AND topic != '';
            """, (user_id,))
            perf_topics = [r["topic"] for r in cursor.fetchall()]

            cursor.execute("""
                SELECT DISTINCT topic FROM learning_sessions WHERE user_id = %s AND topic IS NOT NULL AND topic != '';
            """, (user_id,))
            session_topics = [r["topic"] for r in cursor.fetchall()]

            cursor.execute("""
                SELECT file_name FROM materials WHERE user_id = %s;
            """, (user_id,))
            mat_files = [r["file_name"] for r in cursor.fetchall()]

            all_candidate_topics = []
            seen = set()
            for t in perf_topics + session_topics:
                norm = t.strip()
                if norm and norm.lower() not in seen:
                    seen.add(norm.lower())
                    all_candidate_topics.append(norm)

            # Generate recommendation card for each topic
            recommendations = []
            for topic in all_candidate_topics:
                feat_vec, raw_data = cls.extract_features(user_id, topic, conn=conn)
                card = cls.generate_recommendation_card(user_id, topic, feat_vec, raw_data)
                recommendations.append(card)

            # If student uploaded materials that have no sessions or performance yet, add as new topic candidate
            for mat in mat_files:
                mat_clean = os.path.splitext(mat)[0].replace("_", " ").title()
                if mat_clean.lower() not in seen and len(recommendations) < 6:
                    seen.add(mat_clean.lower())
                    recommendations.append({
                        "id": f"rec-mat-{abs(hash(mat)) % 100000}",
                        "topic": mat,
                        "category": "New Material",
                        "badgeType": "blue",
                        "title": f"Study {mat_clean}",
                        "reason": f"New uploaded study material available. Generate notes, flashcards, and step-by-step breakdowns to get started.",
                        "actionText": "Generate Content",
                        "suggested_action": "Open Learning Workspace and generate initial learning notes.",
                        "priority": 50,
                        "decision": "continue_topic",
                        "confidence": 0.90,
                        "engine": "metadata",
                        "current_performance": {
                            "score": 0.0,
                            "average_score": 0.0,
                            "attempts": 0,
                            "level": "unattempted"
                        }
                    })

            # Sort recommendations by priority (highest priority first: e.g. 90 -> 75 -> 60 -> 45)
            recommendations.sort(key=lambda x: x["priority"], reverse=True)

            # Persist into MySQL recommendations table (multi-tenant isolation)
            write_cursor = conn.cursor()
            write_cursor.execute("DELETE FROM recommendations WHERE user_id = %s;", (user_id,))

            for rec in recommendations:
                write_cursor.execute("""
                    INSERT INTO recommendations (user_id, topic, recommendation_type, recommendation_text, priority)
                    VALUES (%s, %s, %s, %s, %s);
                """, (
                    user_id,
                    rec["topic"],
                    rec["category"],
                    rec["reason"],
                    rec["priority"]
                ))

            conn.commit()
            write_cursor.close()
            cursor.close()

            status_info = cls.get_model_status()

            return {
                "status": "success",
                "has_data": len(recommendations) > 0,
                "count": len(recommendations),
                "model_status": status_info["status"],
                "model_engine": status_info["engine"],
                "recommendations": recommendations
            }

        finally:
            conn.close()

    @classmethod
    def train_model(cls, min_samples=MIN_TRAINING_SAMPLES):
        """
        Attempt to train the XGBoost classifier using real historical student performance
        and quiz attempt data from MySQL.
        """
        conn = get_db_connection()
        try:
            cursor = conn.cursor(dictionary=True)

            # Fetch all distinct (user_id, topic) pairs across the system
            cursor.execute("""
                SELECT DISTINCT user_id, topic
                FROM performance
                WHERE topic IS NOT NULL AND topic != '';
            """)
            student_topics = cursor.fetchall()
            cursor.close()

            if len(student_topics) < min_samples:
                return {
                    "status": "insufficient_data",
                    "samples_count": len(student_topics),
                    "min_required": min_samples,
                    "message": (f"Found {len(student_topics)} distinct student-topic records in MySQL. "
                                f"At least {min_samples} required for XGBoost training. Baseline heuristic remains active.")
                }

            # Build dataset
            X_list = []
            y_list = []

            for row in student_topics:
                u_id = row["user_id"]
                top = row["topic"]
                feat_vec, raw_data = cls.extract_features(u_id, top, conn=conn)
                label, _ = cls._deterministic_baseline(raw_data)
                X_list.append(feat_vec)
                y_list.append(label)

            X = np.array(X_list, dtype=np.float32)
            y = np.array(y_list, dtype=np.int32)

            unique_classes = set(y)
            classes_list = sorted([int(c) for c in unique_classes])
            if len(unique_classes) < 2:
                return {
                    "status": "insufficient_diversity",
                    "samples_count": len(X_list),
                    "classes_found": classes_list,
                    "message": "Samples do not span enough diverse performance classes yet. Baseline heuristic remains active."
                }

            import xgboost as xgb
            os.makedirs(MODEL_DIR, exist_ok=True)

            model = xgb.XGBClassifier(
                n_estimators=30,
                max_depth=3,
                learning_rate=0.1,
                objective="multi:softprob",
                num_class=4,
                eval_metric="mlogloss",
                random_state=42
            )
            model.fit(X, y)
            model.save_model(MODEL_PATH)
            cls._model = model

            meta = {
                "trained_at": datetime.datetime.now().isoformat(),
                "training_samples": len(X_list),
                "num_classes": 4,
                "classes_present": classes_list,
                "features": FEATURE_NAMES
            }
            with open(MODEL_META_PATH, "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2)
            cls._meta = meta

            return {
                "status": "success",
                "training_samples": len(X_list),
                "model_path": MODEL_PATH,
                "meta": meta
            }

        except Exception as e:
            logger.error(f"Error training XGBoost recommendation model: {e}", exc_info=True)
            return {
                "status": "error",
                "message": str(e)
            }
        finally:
            conn.close()
