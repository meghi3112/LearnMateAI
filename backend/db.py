import os
import time
import urllib.parse
import mysql.connector
from dotenv import load_dotenv
import logging

load_dotenv()

logger = logging.getLogger(__name__)

# Core 10 tables defined in strict foreign-key dependency order
TABLE_DEFINITIONS = [
    # 1. users (no foreign keys)
    """CREATE TABLE IF NOT EXISTS `users` (
      `user_id` int NOT NULL AUTO_INCREMENT,
      `full_name` varchar(100) NOT NULL,
      `email` varchar(150) NOT NULL,
      `password_hash` varchar(255) NOT NULL,
      `profile_picture` varchar(255) DEFAULT NULL,
      `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY (`user_id`),
      UNIQUE KEY `email` (`email`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;""",

    # 2. materials (references users)
    """CREATE TABLE IF NOT EXISTS `materials` (
      `material_id` int NOT NULL AUTO_INCREMENT,
      `user_id` int NOT NULL,
      `file_name` varchar(255) NOT NULL,
      `file_type` varchar(20) DEFAULT NULL,
      `file_path` varchar(500) DEFAULT NULL,
      `file_size` bigint DEFAULT NULL,
      `uploaded_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY (`material_id`),
      KEY `user_id` (`user_id`),
      CONSTRAINT `materials_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;""",

    # 3. learning_preferences (references users)
    """CREATE TABLE IF NOT EXISTS `learning_preferences` (
      `preference_id` int NOT NULL AUTO_INCREMENT,
      `user_id` int NOT NULL,
      `simple_concise` int DEFAULT 0,
      `detailed` int DEFAULT 0,
      `step_by_step` int DEFAULT 0,
      `visual` int DEFAULT 0,
      `practice` int DEFAULT 0,
      `revision` int DEFAULT 0,
      `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
      PRIMARY KEY (`preference_id`),
      KEY `user_id` (`user_id`),
      CONSTRAINT `learning_preferences_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;""",

    # 4. learning_sessions (references users, materials)
    """CREATE TABLE IF NOT EXISTS `learning_sessions` (
      `session_id` int NOT NULL AUTO_INCREMENT,
      `user_id` int NOT NULL,
      `material_id` int DEFAULT NULL,
      `topic` varchar(255) NOT NULL,
      `source_type` enum('topic','material') DEFAULT 'topic',
      `started_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
      `completed_at` timestamp NULL DEFAULT NULL,
      PRIMARY KEY (`session_id`),
      KEY `user_id` (`user_id`),
      KEY `material_id` (`material_id`),
      CONSTRAINT `learning_sessions_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE,
      CONSTRAINT `learning_sessions_ibfk_2` FOREIGN KEY (`material_id`) REFERENCES `materials` (`material_id`) ON DELETE SET NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;""",

    # 5. quizzes (references learning_sessions)
    """CREATE TABLE IF NOT EXISTS `quizzes` (
      `quiz_id` int NOT NULL AUTO_INCREMENT,
      `session_id` int NOT NULL,
      `difficulty` enum('easy','medium','hard') DEFAULT 'medium',
      `total_questions` int DEFAULT 10,
      `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY (`quiz_id`),
      KEY `session_id` (`session_id`),
      CONSTRAINT `quizzes_ibfk_1` FOREIGN KEY (`session_id`) REFERENCES `learning_sessions` (`session_id`) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;""",

    # 6. quiz_questions (references quizzes)
    """CREATE TABLE IF NOT EXISTS `quiz_questions` (
      `question_id` int NOT NULL AUTO_INCREMENT,
      `quiz_id` int NOT NULL,
      `question_text` text NOT NULL,
      `option_a` text,
      `option_b` text,
      `option_c` text,
      `option_d` text,
      `correct_answer` char(1) DEFAULT NULL,
      `explanation` text,
      PRIMARY KEY (`question_id`),
      KEY `quiz_id` (`quiz_id`),
      CONSTRAINT `quiz_questions_ibfk_1` FOREIGN KEY (`quiz_id`) REFERENCES `quizzes` (`quiz_id`) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;""",

    # 7. quiz_attempts (references quizzes, users)
    """CREATE TABLE IF NOT EXISTS `quiz_attempts` (
      `attempt_id` int NOT NULL AUTO_INCREMENT,
      `quiz_id` int NOT NULL,
      `user_id` int NOT NULL,
      `score` decimal(5,2) DEFAULT 0.00,
      `total_questions` int DEFAULT 0,
      `attempted_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY (`attempt_id`),
      KEY `quiz_id` (`quiz_id`),
      KEY `user_id` (`user_id`),
      CONSTRAINT `quiz_attempts_ibfk_1` FOREIGN KEY (`quiz_id`) REFERENCES `quizzes` (`quiz_id`) ON DELETE CASCADE,
      CONSTRAINT `quiz_attempts_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;""",

    # 8. generated_resources (references learning_sessions)
    """CREATE TABLE IF NOT EXISTS `generated_resources` (
      `resource_id` int NOT NULL AUTO_INCREMENT,
      `session_id` int NOT NULL,
      `resource_type` enum('simplified_notes','detailed_explanation','step_by_step','summary','flashcards','questions_answers','diagrams','adaptive_quiz') NOT NULL,
      `content` longtext,
      `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY (`resource_id`),
      KEY `session_id` (`session_id`),
      CONSTRAINT `generated_resources_ibfk_1` FOREIGN KEY (`session_id`) REFERENCES `learning_sessions` (`session_id`) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;""",

    # 9. performance (references users, learning_sessions)
    """CREATE TABLE IF NOT EXISTS `performance` (
      `performance_id` int NOT NULL AUTO_INCREMENT,
      `user_id` int NOT NULL,
      `session_id` int DEFAULT NULL,
      `topic` varchar(255) NOT NULL,
      `quiz_score` decimal(5,2) DEFAULT 0.00,
      `attempts` int DEFAULT 0,
      `completion_percentage` decimal(5,2) DEFAULT 0.00,
      `performance_level` enum('needs_improvement','average','good','excellent') DEFAULT 'average',
      `recorded_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY (`performance_id`),
      KEY `user_id` (`user_id`),
      KEY `session_id` (`session_id`),
      CONSTRAINT `performance_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE,
      CONSTRAINT `performance_ibfk_2` FOREIGN KEY (`session_id`) REFERENCES `learning_sessions` (`session_id`) ON DELETE SET NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;""",

    # 10. recommendations (references users)
    """CREATE TABLE IF NOT EXISTS `recommendations` (
      `recommendation_id` int NOT NULL AUTO_INCREMENT,
      `user_id` int NOT NULL,
      `topic` varchar(255) DEFAULT NULL,
      `recommendation_type` varchar(100) DEFAULT NULL,
      `recommendation_text` text,
      `priority` int DEFAULT 1,
      `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY (`recommendation_id`),
      KEY `user_id` (`user_id`),
      CONSTRAINT `recommendations_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;"""
]


def get_db_config(include_database=True):
    """
    Retrieve database configuration parameters from environment with comprehensive fallback support:
    1. MYSQL_URL or DATABASE_URL (standard for Railway, Render, Heroku)
    2. Railway-style un-underscored variables (MYSQLHOST, MYSQLPORT, MYSQLUSER, MYSQLPASSWORD, MYSQLDATABASE)
    3. Standard production variables (MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE)
    4. Project legacy variables (DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME)
    """
    # 1. Check for connection URL string (common in Railway/Heroku/Render)
    db_url = os.getenv('MYSQL_URL') or os.getenv('DATABASE_URL')
    if db_url and (db_url.startswith('mysql://') or db_url.startswith('mysql+pymysql://')):
        parsed = urllib.parse.urlparse(db_url)
        config = {
            'host': parsed.hostname or 'localhost',
            'port': parsed.port or 3306,
            'user': parsed.username or 'root',
            'password': parsed.password or '',
            'charset': 'utf8mb4',
            'use_pure': True,
            'connection_timeout': 10
        }
        if include_database:
            db_name = parsed.path.lstrip('/')
            config['database'] = db_name if db_name else 'learnmate_ai'
        return config

    # 2. Extract configuration from individual environment variables
    host = (
        os.getenv('MYSQLHOST') or
        os.getenv('MYSQL_HOST') or
        os.getenv('DB_HOST') or
        'localhost'
    )
    port_str = (
        os.getenv('MYSQLPORT') or
        os.getenv('MYSQL_PORT') or
        os.getenv('DB_PORT') or
        '3306'
    )
    user = (
        os.getenv('MYSQLUSER') or
        os.getenv('MYSQL_USER') or
        os.getenv('DB_USER') or
        'root'
    )
    password = (
        os.getenv('MYSQLPASSWORD') or
        os.getenv('MYSQL_PASSWORD') or
        os.getenv('DB_PASSWORD') or
        ''
    )
    database = (
        os.getenv('MYSQLDATABASE') or
        os.getenv('MYSQL_DATABASE') or
        os.getenv('DB_NAME') or
        'learnmate_ai'
    )

    try:
        port = int(port_str)
    except (ValueError, TypeError):
        port = 3306

    config = {
        'host': host,
        'port': port,
        'user': user,
        'password': password,
        'charset': 'utf8mb4',
        'use_pure': True,
        'connection_timeout': 10
    }
    if include_database:
        config['database'] = database

    return config


def get_db_connection(include_database=True):
    """
    Establish and return a connection to MySQL database.
    Attempts IPv4 (127.0.0.1) first when host is localhost to prevent Windows IPv6 DNS delay.
    """
    config = get_db_config(include_database=include_database)
    host = config.get('host', 'localhost')
    hosts_to_try = ['127.0.0.1', 'localhost'] if host in ('localhost', '127.0.0.1') else [host]

    last_err = None
    for h in hosts_to_try:
        try:
            cfg = config.copy()
            cfg['host'] = h
            return mysql.connector.connect(**cfg)
        except mysql.connector.Error as err:
            last_err = err

    raise last_err


def init_db(create_db_if_missing=True, max_retries=5, retry_interval=2):
    """
    Automatically initialize database and create all required tables if they do not exist.
    Safe for production environments (e.g. Railway):
    - Retries connection during container startup if MySQL is warming up.
    - Creates target database if it doesn't exist.
    - Idempotently executes CREATE TABLE IF NOT EXISTS for all 10 core tables in foreign key order.
    """
    target_db = (
        os.getenv('MYSQLDATABASE') or
        os.getenv('MYSQL_DATABASE') or
        os.getenv('DB_NAME') or
        'learnmate_ai'
    )
    db_url = os.getenv('MYSQL_URL') or os.getenv('DATABASE_URL')
    if db_url and (db_url.startswith('mysql://') or db_url.startswith('mysql+pymysql://')):
        parsed = urllib.parse.urlparse(db_url)
        if parsed.path.lstrip('/'):
            target_db = parsed.path.lstrip('/')

    logger.info(f"Initializing MySQL database '{target_db}'...")

    # Step 1: Retry loop to establish server connectivity (handles container cold start)
    server_conn = None
    attempt = 0
    while attempt < max_retries:
        attempt += 1
        try:
            if create_db_if_missing:
                server_conn = get_db_connection(include_database=False)
                cursor = server_conn.cursor()
                cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{target_db}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
                cursor.close()
                server_conn.close()
            break
        except Exception as e:
            logger.warning(f"MySQL server connection attempt {attempt}/{max_retries} failed: {e}")
            if attempt < max_retries:
                time.sleep(retry_interval)
            else:
                logger.error(f"Could not connect to MySQL server without database after {max_retries} attempts.")

    # Step 2: Connect directly to target database and create tables
    db_conn = None
    attempt = 0
    while attempt < max_retries:
        attempt += 1
        try:
            db_conn = get_db_connection(include_database=True)
            break
        except Exception as e:
            logger.warning(f"Database '{target_db}' connection attempt {attempt}/{max_retries} failed: {e}")
            if attempt < max_retries:
                time.sleep(retry_interval)
            else:
                logger.error(f"Failed to connect to database '{target_db}' after {max_retries} attempts.")
                return {"status": "error", "error": str(e), "tables_created": 0}

    try:
        cursor = db_conn.cursor()
        created_count = 0
        for ddl in TABLE_DEFINITIONS:
            cursor.execute(ddl)
            created_count += 1
        db_conn.commit()

        # Check existing tables
        cursor.execute("SHOW TABLES;")
        existing_tables = [row[0] for row in cursor.fetchall()]
        cursor.close()
        db_conn.close()

        logger.info(f"Database initialization complete: {len(existing_tables)} tables verified in '{target_db}'.")
        return {
            "status": "success",
            "database_name": target_db,
            "table_count": len(existing_tables),
            "tables": existing_tables
        }
    except Exception as e:
        logger.error(f"Error creating tables in '{target_db}': {e}")
        if db_conn:
            try: db_conn.close()
            except Exception: pass
        return {"status": "error", "error": str(e), "tables_created": 0}


def check_db_health():
    """
    Check the health of the database connection and retrieve available tables.
    Returns a dict with connection status and sanitized details.
    """
    db_name = (
        os.getenv('MYSQLDATABASE') or
        os.getenv('MYSQL_DATABASE') or
        os.getenv('DB_NAME') or
        'learnmate_ai'
    )
    db_url = os.getenv('MYSQL_URL') or os.getenv('DATABASE_URL')
    if db_url and (db_url.startswith('mysql://') or db_url.startswith('mysql+pymysql://')):
        parsed = urllib.parse.urlparse(db_url)
        if parsed.path.lstrip('/'):
            db_name = parsed.path.lstrip('/')

    try:
        conn = get_db_connection(include_database=True)
        cursor = conn.cursor()
        cursor.execute("SELECT DATABASE();")
        current_db = cursor.fetchone()[0]

        cursor.execute("SHOW TABLES;")
        tables = [row[0] for row in cursor.fetchall()]

        cursor.close()
        conn.close()

        return {
            "status": "connected",
            "database_name": current_db,
            "table_count": len(tables),
            "tables": tables
        }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {
            "status": "error",
            "database_name": db_name,
            "error": "Database connection unavailable",
            "table_count": 0,
            "tables": []
        }
