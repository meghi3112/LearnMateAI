import os
import re
import json
import logging
from flask import Blueprint, request, jsonify
from backend.db import get_db_connection
from backend.routes.auth import get_authenticated_user_id, fetch_user_preferences
from backend.rag.extractor import extract_text_from_file
from backend.rag.vector_store import retrieve_material_context, retrieve_material_context_with_metadata, chunk_document_text
from backend.services.gemini_service import (
    generate_all_learning_resources,
    generate_document_grounded_resources,
    validate_grounding,
    validate_resource_quality,
    fetch_topic_knowledge,
    answer_follow_up_query,
    generate_dynamic_adaptive_quiz,
    check_topic_coverage_in_context
)

learning_bp = Blueprint('learning', __name__)
logger = logging.getLogger(__name__)

RESOURCE_TYPE_MAP = {
    "simplified_notes": "simplified_notes",
    "detailed_explanation": "detailed_explanation",
    "step_by_step": "step_by_step",
    "summary": "summary",
    "flashcards": "flashcards",
    "questions_answers": "questions_answers",
    "diagrams": "diagrams",
    "adaptive_quiz": "adaptive_quiz"
}

@learning_bp.route('/api/learning/generate', methods=['POST'])
def generate_content():
    """
    Generate all 8 educational resources for a topic or study material using RAG and Gemini.
    Stores the session, resources, and quiz in MySQL with multi-tenant isolation.
    """
    user_id = get_authenticated_user_id()
    if not user_id:
        return jsonify({"status": "error", "message": "Authentication required."}), 401

    data = request.get_json() or {}
    topic = (data.get('topic') or '').strip()
    material_id = data.get('material_id')

    if material_id:
        try:
            material_id = int(material_id)
        except (ValueError, TypeError):
            material_id = None

    if not topic and not material_id:
        return jsonify({"status": "error", "message": "Please provide a study topic or select an uploaded material."}), 400

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    retrieved_context = None
    doc_text = ""
    source_type = "topic"

    # If material_id is provided, verify ownership and run RAG pipeline
    if material_id:
        cursor.execute("SELECT material_id, file_name, file_type, file_path FROM materials WHERE material_id = %s AND user_id = %s;", (material_id, user_id))
        mat = cursor.fetchone()
        if not mat:
            cursor.close()
            conn.close()
            return jsonify({"status": "error", "message": "Study material not found or unauthorized."}), 404

        source_type = "material"
        file_path = mat['file_path']

        # Derive topic name if not provided or if user sent a follow-up/meta intent phrase
        meta_followup_phrases = ["summarize the topics", "summarize this", "explain this", "give a summary", "make it simple", "revise this"]
        if not topic or any(p in topic.lower() for p in meta_followup_phrases):
            base_name = os.path.splitext(mat['file_name'])[0]
            clean_base = base_name.replace('_', ' ').replace('-', ' ').title()
            topic = clean_base

        # Step 1: Text extraction from PDF/DOCX/PPT
        extract_result = extract_text_from_file(file_path, mat['file_type'])
        if extract_result.get("status") != "success":
            cursor.close()
            conn.close()
            return jsonify({
                "status": "error",
                "message": extract_result.get("message", "Failed to extract text from document.")
            }), 400

        doc_text = extract_result.get("text", "")
        char_count = len(doc_text)
        preview_first = doc_text[:500]
        preview_last = doc_text[-500:] if char_count > 500 else doc_text
        doc_chunks = chunk_document_text(doc_text, chunk_size=750, chunk_overlap=150)
        chunk_count = len(doc_chunks)

        logger.info(f"[RAG EXTRACTION] Material ID: {material_id}, File: {mat['file_name']}, Chars: {char_count}, Chunks: {chunk_count}")
        logger.info(f"[RAG EXTRACTION] First 500 chars:\n{preview_first}")
        logger.info(f"[RAG EXTRACTION] Last 500 chars:\n{preview_last}")

        # Step 2: Vector retrieval using FAISS with strict user_id isolation
        try:
            retrieved_context, retrieved_chunks = retrieve_material_context_with_metadata(
                user_id=user_id,
                material_id=material_id,
                query=topic,
                raw_text=doc_text,
                top_k=6,
                source_file=mat['file_name']
            )
        except Exception as e:
            logger.warning(f"Vector retrieval fallback to raw text: {e}")
            retrieved_context = doc_text[:15000]
            retrieved_chunks = []

        logger.info(f"[RAG RETRIEVAL] User Topic: '{topic}', Material ID: {material_id}")
        logger.info(f"[RAG RETRIEVAL] Retrieved Chunk Count: {len(retrieved_chunks)}")
        for idx, ch in enumerate(retrieved_chunks[:4], 1):
            logger.info(f"[RAG RETRIEVAL] Chunk {idx} preview: {ch.get('text', '')[:120]}...")

    # Fetch student's learning preferences from MySQL
    pref_cursor = conn.cursor()
    preferences = fetch_user_preferences(pref_cursor, user_id)
    pref_cursor.close()

    # Step 3: Call generation engine with section-aware RAG context
    gen_context = retrieved_context if retrieved_context else (doc_text[:15000] if doc_text else None)
    gen_result = generate_all_learning_resources(
        topic=topic,
        context=gen_context,
        preferences=preferences
    )

    if gen_result.get("status") != "success":
        cursor.close()
        conn.close()
        err_msg = gen_result.get("message", "Learning content generation failed.")
        return jsonify({
            "status": "error",
            "message": err_msg,
            "error_type": gen_result.get("error_type")
        }), 500

    resources = gen_result.get("resources", {})
    quiz_questions = gen_result.get("quiz", [])

    # Step 3b: Grounding Validation Check (Material Mode) & Quality Guardrail (Topic-Only Mode)
    if material_id and retrieved_context:
        grounding_check = validate_grounding(resources, context=retrieved_context, topic=topic)
        if not grounding_check.get("is_grounded"):
            err_reason = grounding_check.get("reason", "Generated output failed document grounding validation.")
            logger.warning(f"[GROUNDING VALIDATION] Retrying with deterministic grounded synthesis: {err_reason}")
            fallback_gen = generate_document_grounded_resources(topic=topic, context=retrieved_context, preferences=preferences)
            resources = fallback_gen.get("resources", {})
            quiz_questions = fallback_gen.get("quiz", [])
    else:
        # Topic-Only Quality Guardrail: ensure 0 forbidden filler phrases
        quality_check = validate_resource_quality(resources, topic=topic)
        if not quality_check.get("valid"):
            logger.warning(f"[TOPIC QUALITY CHECK FAILED] {quality_check.get('reason')}. Re-synthesizing via topic knowledge engine...")
            topic_ctx = fetch_topic_knowledge(topic)
            fallback_gen = generate_document_grounded_resources(topic=topic, context=topic_ctx, preferences=preferences)
            resources = fallback_gen.get("resources", {})
            quiz_questions = fallback_gen.get("quiz", [])

    # Step 4: Persist in MySQL
    try:
        # Create learning_sessions record
        cursor.execute("""
            INSERT INTO learning_sessions (user_id, topic, source_type, material_id)
            VALUES (%s, %s, %s, %s);
        """, (user_id, topic, source_type, material_id))
        session_id = cursor.lastrowid

        # Insert all 8 resources into generated_resources
        for res_key, res_enum in RESOURCE_TYPE_MAP.items():
            content_val = resources.get(res_key, "")
            if isinstance(content_val, (dict, list)):
                content_str = json.dumps(content_val, ensure_ascii=False)
            else:
                content_str = str(content_val)

            cursor.execute("""
                INSERT INTO generated_resources (session_id, resource_type, content)
                VALUES (%s, %s, %s);
            """, (session_id, res_enum, content_str))

        # Insert quiz into quizzes table
        cursor.execute("""
            INSERT INTO quizzes (session_id, difficulty, total_questions)
            VALUES (%s, 'medium', %s);
        """, (session_id, len(quiz_questions)))
        quiz_id = cursor.lastrowid

        # Insert quiz questions into quiz_questions table
        stored_questions = []
        for q in quiz_questions:
            q_text = q.get("question", "")
            opt_a = q.get("option_a", "")
            opt_b = q.get("option_b", "")
            opt_c = q.get("option_c", "")
            opt_d = q.get("option_d", "")
            correct = (q.get("correct_answer") or "A").strip().upper()[:1]
            explanation = q.get("explanation", "")

            cursor.execute("""
                INSERT INTO quiz_questions (quiz_id, question_text, option_a, option_b, option_c, option_d, correct_answer, explanation)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
            """, (quiz_id, q_text, opt_a, opt_b, opt_c, opt_d, correct, explanation))
            
            q_id = cursor.lastrowid
            stored_questions.append({
                "id": q_id,
                "question": q_text,
                "option_a": opt_a,
                "option_b": opt_b,
                "option_c": opt_c,
                "option_d": opt_d,
                "correct_answer": correct,
                "explanation": explanation,
                "difficulty": q.get("difficulty", "medium")
            })

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({
            "status": "success",
            "message": f'Personalized learning pack generated for "{topic}".',
            "session_id": session_id,
            "topic": topic,
            "material_id": material_id,
            "quiz_id": quiz_id,
            "resources": resources,
            "quiz_questions": stored_questions
        }), 201

    except Exception as e:
        logger.error(f"Database insertion failed during generation: {e}", exc_info=True)
        try: cursor.close(); conn.close()
        except Exception: pass
        return jsonify({"status": "error", "message": f"Failed to save generated resources: {str(e)}"}), 500


def parse_quiz_intent(message: str):
    """
    Detect if student is requesting a quiz and extract target topic and scope.
    Returns: (is_quiz_request, topic_name, is_whole_material)
    """
    msg_clean = message.strip()
    msg_lower = msg_clean.lower().rstrip(".!?")

    # Whole-material quiz triggers
    whole_material_phrases = {
        "quiz me on this material", "quiz me on this", "quiz me on the whole material",
        "quiz me on the whole topic", "give me a complete quiz", "quiz me on everything",
        "quiz me on all topics", "test me on this material", "test me on the whole material",
        "test me on everything", "give me a quiz on this", "quiz me", "test me", "give me a quiz",
        "ask me questions", "test my understanding", "quiz on this material", "quiz on the whole material",
        "give a quiz on this", "give a quiz", "test my knowledge", "knowledge check"
    }
    if msg_lower in whole_material_phrases:
        return True, "Whole Material", True

    patterns = [
        r"^(?:quiz|test)\s+me\s+(?:on|about)\s+(.+)$",
        r"^(?:give|create|generate)\s+(?:me\s+)?(?:a\s+)?quiz\s+(?:on|about)\s+(.+)$",
        r"^(?:ask|test)\s+(?:me\s+)?(?:questions|understanding)\s+(?:on|about)\s+(.+)$",
        r"^quiz\s+(?:on|about)\s+(.+)$",
        r"^practice\s+quiz\s+(?:on|about)\s+(.+)$"
    ]
    for pat in patterns:
        m = re.match(pat, msg_lower, re.IGNORECASE)
        if m:
            extracted = m.group(1).strip().strip("?.!\"'")
            if extracted in ("this", "this material", "the material", "the whole material", "the whole topic", "everything", "all", "all topics"):
                return True, "Whole Material", True
            return True, extracted, False

    return False, "", False


def generate_quiz_for_session(
    user_id: int,
    session_id,
    material_id,
    topic_query: str,
    is_whole_material: bool = False
):
    """
    Core dynamic quiz generation pipeline:
    1. Resolve user, session, and material ownership.
    2. Retrieve validated RAG context:
       - If whole material: sample balanced passages across the document.
       - If specific topic: retrieve targeted chunks for topic query and verify coverage.
    3. Call Gemini dynamic quiz generator (or dynamic grounded fallback).
    4. Persist generated quiz in quizzes and quiz_questions tables.
    5. Return structured quiz object.
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    session_row = None
    if session_id:
        try:
            cursor.execute("SELECT session_id, user_id, material_id, topic FROM learning_sessions WHERE session_id = %s AND user_id = %s;", (session_id, user_id))
            session_row = cursor.fetchone()
            if session_row and not material_id:
                material_id = session_row.get("material_id")
        except Exception as e:
            logger.warning(f"Error looking up session {session_id}: {e}")

    if not session_id and material_id:
        try:
            cursor.execute("SELECT session_id, topic FROM learning_sessions WHERE user_id = %s AND material_id = %s ORDER BY session_id DESC LIMIT 1;", (user_id, material_id))
            session_row = cursor.fetchone()
            if session_row:
                session_id = session_row["session_id"]
        except Exception as e:
            logger.warning(f"Error looking up material session: {e}")

    # If topic_query is generic or empty, use session topic or material title
    clean_topic = (topic_query or "").strip()
    if is_whole_material or not clean_topic or clean_topic.lower() in ("whole material", "this", "this material", "the material"):
        if session_row and session_row.get("topic"):
            clean_topic = session_row["topic"]
        else:
            clean_topic = "Course Material"

    # Context retrieval
    doc_text = ""
    retrieved_context = None
    doc_name = None

    if material_id:
        try:
            cursor.execute("SELECT material_id, file_name, file_path, file_type FROM materials WHERE material_id = %s AND user_id = %s;", (material_id, user_id))
            mat = cursor.fetchone()
            if mat:
                doc_name = mat["file_name"]
                file_path = mat["file_path"]
                if os.path.exists(file_path):
                    extract_res = extract_text_from_file(file_path, mat["file_type"])
                    if extract_res.get("status") == "success":
                        doc_text = extract_res.get("text", "")
                        if is_whole_material:
                            if len(doc_text) <= 25000:
                                retrieved_context = doc_text
                            else:
                                chunks = chunk_document_text(doc_text, chunk_size=750, chunk_overlap=100)
                                step = max(1, len(chunks) // 10)
                                sampled = [chunks[i] for i in range(0, len(chunks), step)][:10]
                                retrieved_context = "\n\n---\n\n".join(sampled)
                        else:
                            # Specific topic retrieval
                            try:
                                retrieved_context, _ = retrieve_material_context_with_metadata(
                                    user_id=user_id,
                                    material_id=material_id,
                                    query=clean_topic,
                                    raw_text=doc_text,
                                    top_k=8,
                                    source_file=doc_name
                                )
                            except Exception:
                                retrieved_context = doc_text[:15000]

                            # Grounding coverage check: verify topic exists in document
                            if not check_topic_coverage_in_context(clean_topic, doc_text):
                                cursor.close()
                                conn.close()
                                return {
                                    "status": "error",
                                    "message": "The requested topic is not covered in the uploaded material. Please choose another topic from the document or ask for a quiz on the whole material.",
                                    "topic_not_covered": True,
                                    "quiz_questions": []
                                }
        except Exception as e:
            logger.error(f"Error during material lookup or extraction for quiz: {e}")

    # If no session exists, create a session
    if not session_id:
        source_type = "material" if material_id else "topic"
        cursor.execute("INSERT INTO learning_sessions (user_id, topic, source_type, material_id) VALUES (%s, %s, %s, %s);", (user_id, clean_topic, source_type, material_id))
        session_id = cursor.lastrowid

    # Fetch preferences
    pref_cursor = conn.cursor()
    preferences = fetch_user_preferences(pref_cursor, user_id)
    pref_cursor.close()

    # Generate quiz using dedicated dynamic generator
    quiz_res = generate_dynamic_adaptive_quiz(
        topic=clean_topic,
        context=retrieved_context,
        preferences=preferences,
        is_whole_material=is_whole_material,
        doc_name=doc_name
    )

    if quiz_res.get("topic_not_covered"):
        cursor.close()
        conn.close()
        return {
            "status": "error",
            "message": "The requested topic is not covered in the uploaded material. Please choose another topic from the document or ask for a quiz on the whole material.",
            "topic_not_covered": True,
            "quiz_questions": []
        }

    quiz_questions = quiz_res.get("quiz", [])
    if not quiz_questions:
        cursor.close()
        conn.close()
        return {"status": "error", "message": "Failed to generate dynamic quiz.", "quiz_questions": []}

    # Store quiz in MySQL
    cursor.execute("""
        INSERT INTO quizzes (session_id, difficulty, total_questions)
        VALUES (%s, 'medium', %s);
    """, (session_id, len(quiz_questions)))
    quiz_id = cursor.lastrowid

    stored_questions = []
    for q in quiz_questions:
        q_text = q.get("question", "")
        opt_a = q.get("option_a", "")
        opt_b = q.get("option_b", "")
        opt_c = q.get("option_c", "")
        opt_d = q.get("option_d", "")
        correct = (q.get("correct_answer") or "A").strip().upper()[:1]
        explanation = q.get("explanation", "")

        cursor.execute("""
            INSERT INTO quiz_questions (quiz_id, question_text, option_a, option_b, option_c, option_d, correct_answer, explanation)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
        """, (quiz_id, q_text, opt_a, opt_b, opt_c, opt_d, correct, explanation))

        stored_questions.append({
            "id": cursor.lastrowid,
            "question": q_text,
            "option_a": opt_a,
            "option_b": opt_b,
            "option_c": opt_c,
            "option_d": opt_d,
            "correct_answer": correct,
            "explanation": explanation,
            "difficulty": q.get("difficulty", "medium")
        })

    # Update or insert generated_resources adaptive_quiz
    try:
        cursor.execute("SELECT resource_id FROM generated_resources WHERE session_id = %s AND resource_type = 'adaptive_quiz' LIMIT 1;", (session_id,))
        res_row = cursor.fetchone()
        quiz_json_str = json.dumps(quiz_questions, ensure_ascii=False)
        if res_row:
            cursor.execute("UPDATE generated_resources SET content = %s WHERE resource_id = %s;", (quiz_json_str, res_row["resource_id"]))
        else:
            cursor.execute("INSERT INTO generated_resources (session_id, resource_type, content) VALUES (%s, 'adaptive_quiz', %s);", (session_id, quiz_json_str))
    except Exception as e:
        logger.warning(f"Could not update generated_resources: {e}")

    conn.commit()
    cursor.close()
    conn.close()

    return {
        "status": "success",
        "quiz_id": quiz_id,
        "session_id": session_id,
        "topic": clean_topic,
        "material_id": material_id,
        "material_name": doc_name,
        "quiz_questions": stored_questions,
        "model_used": quiz_res.get("model_used", "gemini")
    }


@learning_bp.route('/api/learning/quiz/generate', methods=['POST'])
def generate_quiz_endpoint():
    """
    Dedicated endpoint to dynamically generate a 10-question adaptive quiz on demand
    for an active material, specific topic, or whole material.
    """
    user_id = get_authenticated_user_id()
    if not user_id:
        return jsonify({"status": "error", "message": "Authentication required."}), 401

    data = request.get_json() or {}
    topic = (data.get('topic') or data.get('query') or '').strip()
    material_id = data.get('material_id')
    session_id = data.get('session_id')
    is_whole = data.get('is_whole_material', False)

    if not is_whole and topic.lower() in ("this", "the material", "this material", "the whole material", "whole material", "all"):
        is_whole = True

    res = generate_quiz_for_session(
        user_id=user_id,
        session_id=session_id,
        material_id=material_id,
        topic_query=topic,
        is_whole_material=is_whole
    )

    status_code = 200 if res.get("status") == "success" else 400
    return jsonify(res), status_code


@learning_bp.route('/api/learning/chat', methods=['POST'])
def handle_chat_message():
    """
    Intelligently handles student chat follow-up messages with strict context priority:
    Student follow-up request -> Current session -> Current material -> Extracted text -> RAG retrieval -> Gemini -> Grounded Answer.
    If student requests a quiz (e.g. 'Quiz me on Factory Method'), dynamically generates 10 MCQs and returns quiz payload.
    If no active material/session: answers in topic-only mode.
    """
    user_id = get_authenticated_user_id()
    if not user_id:
        return jsonify({"status": "error", "message": "Authentication required."}), 401

    data = request.get_json() or {}
    message = (data.get('message') or data.get('query') or '').strip()
    session_id = data.get('session_id')
    material_id = data.get('material_id')

    if not message:
        return jsonify({"status": "error", "message": "Message content is required."}), 400

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    session_row = None
    if session_id:
        try:
            cursor.execute("SELECT session_id, topic, material_id FROM learning_sessions WHERE session_id = %s AND user_id = %s;", (session_id, user_id))
            session_row = cursor.fetchone()
            if session_row and not material_id:
                material_id = session_row.get("material_id")
        except Exception as e:
            logger.warning(f"Could not look up session {session_id}: {e}")

    # Check if the message is requesting an adaptive quiz
    is_quiz_req, quiz_topic, is_whole = parse_quiz_intent(message)
    if is_quiz_req:
        target_topic = quiz_topic
        if (is_whole or not target_topic or target_topic == "Whole Material") and session_row and session_row.get("topic"):
            target_topic = session_row["topic"]

        cursor.close()
        conn.close()

        quiz_res = generate_quiz_for_session(
            user_id=user_id,
            session_id=session_id,
            material_id=material_id,
            topic_query=target_topic,
            is_whole_material=is_whole
        )

        if quiz_res.get("topic_not_covered"):
            return jsonify({
                "status": "success",
                "reply": "The requested topic is not covered in the uploaded material. Please choose another topic from the document or ask for a quiz on the whole material.",
                "is_quiz": False,
                "not_covered": True,
                "topic_not_covered": True,
                "grounded": True,
                "material_id": material_id,
                "session_id": session_id
            }), 200

        if quiz_res.get("status") == "success":
            return jsonify({
                "status": "success",
                "reply": f"### 🎯 Adaptive Quiz: {quiz_res.get('topic', target_topic)}\n\nHere are 10 dynamic questions generated from your active material. Select your answers below and click **Submit Quiz**:",
                "is_quiz": True,
                "quiz_id": quiz_res["quiz_id"],
                "session_id": quiz_res["session_id"],
                "topic": quiz_res["topic"],
                "quiz_questions": quiz_res["quiz_questions"],
                "grounded": True,
                "material_id": material_id
            }), 200

    mat_row = None
    retrieved_context = None
    doc_name = None

    if material_id:
        try:
            cursor.execute("SELECT material_id, file_name, file_path, file_type FROM materials WHERE material_id = %s AND user_id = %s;", (material_id, user_id))
            mat_row = cursor.fetchone()
        except Exception as e:
            logger.warning(f"Could not look up material {material_id}: {e}")

    if mat_row:
        doc_name = mat_row["file_name"]
        file_path = mat_row["file_path"]
        if os.path.exists(file_path):
            extract_res = extract_text_from_file(file_path, mat_row["file_type"])
            if extract_res.get("status") == "success":
                doc_text = extract_res.get("text", "")
                try:
                    retrieved_context, _ = retrieve_material_context_with_metadata(
                        user_id=user_id,
                        material_id=material_id,
                        query=message,
                        raw_text=doc_text,
                        top_k=6,
                        source_file=doc_name
                    )
                except Exception:
                    retrieved_context = doc_text[:15000]

    # Fetch preferences
    preferences = fetch_user_preferences(cursor, user_id)
    cursor.close()
    conn.close()

    ans = answer_follow_up_query(
        query=message,
        context=retrieved_context,
        material_name=doc_name,
        session_topic=(session_row.get("topic") if session_row else None),
        preferences=preferences
    )

    return jsonify({
        "status": "success",
        "reply": ans.get("reply", ""),
        "grounded": ans.get("grounded", False),
        "material_id": material_id,
        "material_name": doc_name,
        "session_id": session_id,
        "model_used": ans.get("model_used")
    }), 200


@learning_bp.route('/api/learning/sessions/<int:session_id>', methods=['GET'])
def get_session_resources(session_id):
    """
    Retrieve all 8 saved resources and quiz questions for a previous learning session.
    Enforces strict multi-tenant isolation.
    """
    user_id = get_authenticated_user_id()
    if not user_id:
        return jsonify({"status": "error", "message": "Authentication required."}), 401

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Verify session ownership
        cursor.execute("""
            SELECT s.session_id, s.topic, s.source_type, s.material_id, s.started_at, m.file_name as material_name
            FROM learning_sessions s
            LEFT JOIN materials m ON s.material_id = m.material_id
            WHERE s.session_id = %s AND s.user_id = %s;
        """, (session_id, user_id))
        session_row = cursor.fetchone()

        if not session_row:
            cursor.close()
            conn.close()
            return jsonify({"status": "error", "message": "Learning session not found or unauthorized."}), 404

        # Fetch all generated resources
        cursor.execute("""
            SELECT resource_type, content
            FROM generated_resources
            WHERE session_id = %s;
        """, (session_id,))
        res_rows = cursor.fetchall()

        resources = {}
        for r in res_rows:
            r_type = r["resource_type"]
            raw_content = r["content"]
            if r_type in ("flashcards", "questions_answers", "adaptive_quiz", "diagrams"):
                try:
                    resources[r_type] = json.loads(raw_content)
                except Exception:
                    resources[r_type] = raw_content
            else:
                resources[r_type] = raw_content

        # Fetch quiz information
        cursor.execute("SELECT quiz_id, total_questions FROM quizzes WHERE session_id = %s LIMIT 1;", (session_id,))
        quiz_row = cursor.fetchone()

        quiz_id = None
        quiz_questions = []
        if quiz_row:
            quiz_id = quiz_row["quiz_id"]
            cursor.execute("""
                SELECT question_id as id, question_text as question, option_a, option_b, option_c, option_d, explanation
                FROM quiz_questions
                WHERE quiz_id = %s;
            """, (quiz_id,))
            quiz_questions = cursor.fetchall()

        cursor.close()
        conn.close()

        return jsonify({
            "status": "success",
            "session": {
                "session_id": session_row["session_id"],
                "topic": session_row["topic"],
                "source_type": session_row["source_type"],
                "material_id": session_row["material_id"],
                "material_name": session_row["material_name"],
                "started_at": session_row["started_at"].isoformat() if session_row["started_at"] else None
            },
            "quiz_id": quiz_id,
            "resources": resources,
            "quiz_questions": quiz_questions
        }), 200

    except Exception as e:
        logger.error(f"Error retrieving session resources: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500


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


@learning_bp.route('/api/learning/quiz-submit', methods=['POST'])
def submit_quiz():
    """
    Grade student quiz answers against stored question answers, record attempt in MySQL,
    and update student's topic performance level.
    """
    user_id = get_authenticated_user_id()
    if not user_id:
        return jsonify({"status": "error", "message": "Authentication required."}), 401

    data = request.get_json() or {}
    quiz_id = data.get('quiz_id')
    session_id = data.get('session_id')
    user_answers = data.get('answers') or {}  # Dict of {str(question_id): 'A'|'B'|'C'|'D'}

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Resolve quiz_id and session_id with multi-tenant verification
        if not quiz_id and session_id:
            cursor.execute("SELECT quiz_id FROM quizzes WHERE session_id = %s LIMIT 1;", (session_id,))
            q_row = cursor.fetchone()
            if q_row:
                quiz_id = q_row["quiz_id"]

        if quiz_id and not session_id:
            cursor.execute("SELECT session_id FROM quizzes WHERE quiz_id = %s LIMIT 1;", (quiz_id,))
            q_row = cursor.fetchone()
            if q_row:
                session_id = q_row["session_id"]

        if not quiz_id:
            cursor.close()
            conn.close()
            return jsonify({"status": "error", "message": "Quiz ID or valid session_id is required."}), 400

        # Retrieve questions and correct answers for this quiz
        cursor.execute("""
            SELECT question_id, correct_answer, explanation
            FROM quiz_questions
            WHERE quiz_id = %s
            ORDER BY question_id ASC;
        """, (quiz_id,))
        questions = cursor.fetchall()

        if not questions:
            cursor.close()
            conn.close()
            return jsonify({"status": "error", "message": "Quiz questions not found."}), 404

        total_questions = len(questions)
        correct_count = 0
        detailed_results = []

        for q in questions:
            qid_str = str(q['question_id'])
            correct_ans = (q['correct_answer'] or '').strip().upper()
            student_ans = (user_answers.get(qid_str) or user_answers.get(q['question_id']) or '').strip().upper()
            is_correct = (student_ans == correct_ans)
            if is_correct:
                correct_count += 1

            detailed_results.append({
                "question_id": q['question_id'],
                "student_answer": student_ans,
                "correct_answer": correct_ans,
                "is_correct": is_correct,
                "explanation": q['explanation']
            })

        score = round((correct_count / total_questions) * 100.0, 2)
        attempt_level = get_performance_level(score)

        # Record attempt in quiz_attempts
        cursor.execute("""
            INSERT INTO quiz_attempts (quiz_id, user_id, score, total_questions)
            VALUES (%s, %s, %s, %s);
        """, (quiz_id, user_id, score, total_questions))
        attempt_id = cursor.lastrowid

        # Mark learning session as completed
        if session_id:
            cursor.execute("""
                UPDATE learning_sessions
                SET completed_at = CURRENT_TIMESTAMP
                WHERE session_id = %s AND user_id = %s;
            """, (session_id, user_id))

        # Look up session topic
        topic = "General Subject"
        if session_id:
            cursor.execute("SELECT topic FROM learning_sessions WHERE session_id = %s;", (session_id,))
            s_row = cursor.fetchone()
            if s_row and s_row["topic"]:
                topic = s_row["topic"]

        # Update or insert performance record for this user and topic
        cursor.execute("""
            SELECT performance_id, attempts, quiz_score
            FROM performance
            WHERE user_id = %s AND topic = %s
            LIMIT 1;
        """, (user_id, topic))
        perf_row = cursor.fetchone()

        if perf_row:
            old_attempts = perf_row['attempts'] or 0
            old_score = float(perf_row['quiz_score'] or 0.0)
            new_attempts = old_attempts + 1
            new_avg = round(((old_score * old_attempts) + score) / new_attempts, 2)
            overall_level = get_performance_level(new_avg)

            cursor.execute("""
                UPDATE performance
                SET quiz_score = %s, attempts = %s, completion_percentage = 100.0, performance_level = %s, session_id = %s, recorded_at = CURRENT_TIMESTAMP
                WHERE performance_id = %s;
            """, (new_avg, new_attempts, overall_level, session_id, perf_row['performance_id']))
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
            from backend.services.recommendation_service import RecommendationService
            RecommendationService.generate_recommendations_for_user(user_id)
        except Exception as rec_err:
            logger.warning(f"Could not auto-refresh recommendations for user {user_id}: {rec_err}")

        return jsonify({
            "status": "success",
            "message": f"Quiz submitted. You scored {score:.0f}% ({correct_count}/{total_questions}).",
            "attempt_id": attempt_id,
            "score": score,
            "correct_count": correct_count,
            "total_questions": total_questions,
            "performance_level": overall_level,
            "attempt_level": attempt_level,
            "results": detailed_results
        }), 200

    except Exception as e:
        logger.error(f"Error evaluating quiz submission: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500


@learning_bp.route('/api/learning/diagram/generate', methods=['POST'])
def generate_specific_diagram():
    """
    Generate or switch to a specific diagram type (or auto) for a topic, concept, and study material.
    Supports all 7 diagram types with distinct concept-grounded layouts.
    """
    data = request.get_json() or {}
    topic = (data.get('topic') or '').strip()
    concept = (data.get('concept') or '').strip()
    material_id = data.get('material_id')
    diagram_type = (data.get('diagram_type') or 'auto').strip().lower()

    if not topic:
        return jsonify({"status": "error", "message": "Topic is required"}), 400

    context = ""
    if material_id:
        try:
            user_id = get_authenticated_user_id()
            from backend.rag.vector_store import query_vector_store
            concept_query = f"{topic} {concept}" if concept else topic
            rag_results = query_vector_store(user_id=user_id, material_id=int(material_id), query_text=concept_query, top_k=4)
            if rag_results:
                context = "\n\n".join(r["text"] for r in rag_results)
            else:
                conn = get_db_connection()
                cursor = conn.cursor(dictionary=True)
                cursor.execute("SELECT file_path, file_type FROM materials WHERE material_id = %s AND user_id = %s;", (material_id, user_id))
                mat = cursor.fetchone()
                cursor.close()
                conn.close()
                if mat:
                    extract_res = extract_text_from_file(mat['file_path'], mat['file_type'])
                    context = extract_res.get("text", "")[:15000]
        except Exception as e:
            logger.warning(f"Could not retrieve material context for diagram: {e}")

    from backend.services.visual_diagram_service import assemble_visual_learning_bundle
    bundle = assemble_visual_learning_bundle(
        topic=topic,
        context=context if context else None,
        requested_type=None if diagram_type == 'auto' else diagram_type,
        requested_concept=concept or None
    )

    return jsonify({
        "status": "success",
        "diagram_bundle": bundle
    }), 200


@learning_bp.route('/api/learning/diagram/references', methods=['GET'])
def get_diagram_references():
    """
    Fetch trusted open educational reference diagrams from Wikimedia Commons / Wikipedia
    strictly validated for the topic and concept.
    """
    topic = request.args.get('topic', '').strip()
    concept = request.args.get('concept', '').strip()
    diagram_type = request.args.get('diagram_type', '').strip()
    if not topic:
        return jsonify({"status": "error", "message": "Topic is required"}), 400

    from backend.services.visual_diagram_service import search_concept_reference_diagrams
    ref_diagrams = search_concept_reference_diagrams(
        topic=topic,
        concept_name=concept or topic,
        diagram_type=diagram_type or None,
        max_results=4
    )

    return jsonify({
        "status": "success",
        "topic": topic,
        "concept": concept,
        "reference_diagrams": ref_diagrams
    }), 200


@learning_bp.route('/api/learning/diagram/concepts', methods=['GET'])
def get_diagram_concepts():
    """
    Extract and return the important educational concepts for a topic/material with their recommended diagram types.
    """
    topic = request.args.get('topic', '').strip()
    material_id = request.args.get('material_id')
    if not topic:
        return jsonify({"status": "error", "message": "Topic is required"}), 400

    context = ""
    if material_id:
        try:
            user_id = get_authenticated_user_id()
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT file_path, file_type FROM materials WHERE material_id = %s AND user_id = %s;", (material_id, user_id))
            mat = cursor.fetchone()
            cursor.close()
            conn.close()
            if mat:
                extract_res = extract_text_from_file(mat['file_path'], mat['file_type'])
                context = extract_res.get("text", "")[:15000]
        except Exception as e:
            logger.warning(f"Could not retrieve material context for concepts: {e}")

    from backend.services.visual_diagram_service import extract_important_concepts
    concepts = extract_important_concepts(topic=topic, context=context if context else None)

    return jsonify({
        "status": "success",
        "topic": topic,
        "concepts": concepts
    }), 200


