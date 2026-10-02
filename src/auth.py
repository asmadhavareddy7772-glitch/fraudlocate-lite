"""
FraudLocate Lite - Role-Based Authentication & User Management.
Provides secure password hashing (PBKDF2-HMAC-SHA256 with cryptographic salt),
SQLite user persistence in data/alerts.db, and role-based access control (ADMIN/ANALYST and POLICE).
No plaintext passwords are ever stored or exposed.
"""

import os
import sqlite3
import hashlib
import secrets
from datetime import datetime
from typing import Dict, Any, List, Optional

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "alerts.db")

ROLES = ["ANALYST", "POLICE"]


def get_db_connection(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Create or return a thread-safe connection with dict-like row access."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=15.0)
    conn.row_factory = sqlite3.Row
    return conn


def hash_password(password: str, salt: Optional[str] = None) -> tuple[str, str]:
    """
    Hash a password using PBKDF2-HMAC-SHA256 with 100,000 iterations.
    Returns (salt_hex, hash_hex).
    """
    if not salt:
        salt_bytes = secrets.token_bytes(16)
        salt_hex = salt_bytes.hex()
    else:
        salt_bytes = bytes.fromhex(salt)
        salt_hex = salt

    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt_bytes,
        100000,
    )
    return salt_hex, key.hex()


def verify_password(password: str, salt: str, expected_hash: str) -> bool:
    """Securely compare a plaintext candidate password against stored salt and hash."""
    _, candidate_hash = hash_password(password, salt=salt)
    return secrets.compare_digest(candidate_hash, expected_hash)


def init_user_db(db_path: str = DEFAULT_DB_PATH) -> None:
    """Initialize the users table in the persistent SQLite database."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                police_id TEXT UNIQUE,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                role TEXT NOT NULL,
                full_name TEXT NOT NULL,
                badge_number TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_police_id ON users(police_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)")
        conn.commit()


def seed_demo_users_if_empty(db_path: str = DEFAULT_DB_PATH) -> None:
    """Seed baseline demo accounts for Analyst and Police roles if none exist."""
    init_user_db(db_path)
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        count = cursor.fetchone()[0]
        if count == 0:
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            demo_accounts = [
                {
                    "user_id": "USR-ANALYST-001",
                    "username": "analyst",
                    "police_id": None,
                    "password": "analyst123",
                    "role": "ANALYST",
                    "full_name": "Senior Cyber Fraud Analyst",
                    "badge_number": None,
                    "created_at": now_str,
                },
                {
                    "user_id": "USR-POLICE-101",
                    "username": "officer.vikram",
                    "police_id": "TS-POLICE-101",
                    "password": "police101",
                    "role": "POLICE",
                    "full_name": "Inspector Vikram Reddy",
                    "badge_number": "TS-CYB-01",
                    "created_at": now_str,
                },
                {
                    "user_id": "USR-POLICE-102",
                    "username": "officer.ananya",
                    "police_id": "TS-POLICE-102",
                    "password": "police102",
                    "role": "POLICE",
                    "full_name": "Sub-Inspector Ananya Sharma",
                    "badge_number": "TS-CYB-02",
                    "created_at": now_str,
                },
            ]

            for acc in demo_accounts:
                salt, pwd_hash = hash_password(acc["password"])
                cursor.execute(
                    """
                    INSERT INTO users (
                        user_id, username, police_id, password_hash, salt,
                        role, full_name, badge_number, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        acc["user_id"],
                        acc["username"],
                        acc["police_id"],
                        pwd_hash,
                        salt,
                        acc["role"],
                        acc["full_name"],
                        acc["badge_number"],
                        acc["created_at"],
                    ),
                )
            conn.commit()


def authenticate_user(
    login_id: str,
    password: str,
    required_role: Optional[str] = None,
    db_path: str = DEFAULT_DB_PATH,
) -> Optional[Dict[str, Any]]:
    """
    Authenticate a user by username or police_id with password.
    Optionally enforces a specific role (e.g. 'POLICE' or 'ANALYST').
    Returns user dictionary (without sensitive hash/salt) or None.
    """
    init_user_db(db_path)
    seed_demo_users_if_empty(db_path)

    clean_id = (login_id or "").strip()
    if not clean_id or not password:
        return None

    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM users
            WHERE LOWER(username) = LOWER(?) OR LOWER(COALESCE(police_id, '')) = LOWER(?)
            """,
            (clean_id, clean_id),
        )
        row = cursor.fetchone()
        if not row:
            return None

        user_dict = dict(row)
        salt = user_dict.get("salt", "")
        pwd_hash = user_dict.get("password_hash", "")

        if not verify_password(password, salt, pwd_hash):
            return None

        if required_role and user_dict.get("role") != required_role:
            return None

        # Return clean user profile without credentials
        return {
            "user_id": user_dict["user_id"],
            "username": user_dict["username"],
            "police_id": user_dict.get("police_id"),
            "role": user_dict["role"],
            "full_name": user_dict["full_name"],
            "badge_number": user_dict.get("badge_number"),
            "created_at": user_dict["created_at"],
        }


def get_user_by_id(user_id: str, db_path: str = DEFAULT_DB_PATH) -> Optional[Dict[str, Any]]:
    """Fetch user profile by user_id."""
    init_user_db(db_path)
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if not row:
            return None
        u = dict(row)
        u.pop("password_hash", None)
        u.pop("salt", None)
        return u


def get_all_police_officers(db_path: str = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """Retrieve list of registered police officers for assignment/audit displays."""
    init_user_db(db_path)
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, username, police_id, role, full_name, badge_number FROM users WHERE role = 'POLICE' ORDER BY full_name")
        rows = cursor.fetchall()
        return [dict(r) for r in rows]
