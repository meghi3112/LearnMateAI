import os
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

import logging

logger = logging.getLogger(__name__)

def get_db_config():
    """Retrieve database configuration parameters from environment with fallback support."""
    return {
        'host': os.getenv('MYSQL_HOST') or os.getenv('DB_HOST', 'localhost'),
        'port': int(os.getenv('MYSQL_PORT') or os.getenv('DB_PORT', 3306)),
        'user': os.getenv('MYSQL_USER') or os.getenv('DB_USER', 'root'),
        'password': os.getenv('MYSQL_PASSWORD') or os.getenv('DB_PASSWORD', ''),
        'database': os.getenv('MYSQL_DATABASE') or os.getenv('DB_NAME', 'learnmate_ai'),
        'charset': 'utf8mb4',
        'use_pure': True,
        'connection_timeout': 5
    }

def get_db_connection():
    """
    Establish and return a connection to MySQL database.
    Attempts IPv4 (127.0.0.1) first when host is localhost to prevent Windows IPv6 DNS delay.
    """
    config = get_db_config()
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

def check_db_health():
    """
    Check the health of the database connection and retrieve available tables.
    Returns a dict with connection status and sanitized details.
    """
    db_name = os.getenv('MYSQL_DATABASE') or os.getenv('DB_NAME', 'learnmate_ai')
    try:
        conn = get_db_connection()
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
