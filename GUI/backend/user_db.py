"""
User database abstraction using sqlite3.
Provides functions for creating users and verifying credentials.
Implements safe password hashing using pbkdf2_hmac with salt.

Moved from GUI/db.py -- the global DB instance is removed;
callers should create their own UserDatabase instance.
"""
from __future__ import annotations
import sqlite3
from pathlib import Path
import hashlib
import secrets
from typing import Optional

from shared.constants import USER_DB_PATH, ADMIN_PASSWORD


class UserDatabase:
    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = Path(db_path) if db_path else USER_DB_PATH
        self._conn = sqlite3.connect(self.db_path)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                salt TEXT NOT NULL,
                pwd_hash TEXT NOT NULL,
                email TEXT
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS password_reset_tokens (
                id INTEGER PRIMARY KEY,
                username TEXT NOT NULL,
                token TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (username) REFERENCES users (username)
            )
            """
        )
        self._conn.commit()

    def _hash_password(self, password: str, salt_hex: str) -> str:
        salt = bytes.fromhex(salt_hex)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
        return dk.hex()

    def create_user(self, username: str, password: str, email: str = "") -> bool:
        username = username.strip()
        email = email.strip()
        if not username or not password:
            return False
        if self.username_exists(username) or (email and self.email_exists(email)):
            return False
        salt = secrets.token_hex(16)
        pwd_hash = self._hash_password(password, salt)
        try:
            with self._conn:
                self._conn.execute(
                    "INSERT INTO users (username, salt, pwd_hash, email) VALUES (?, ?, ?, ?)",
                    (username, salt, pwd_hash, email),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    # --- Admin-protected operations ------------------------------------------------
    def _check_admin(self, password: str) -> bool:
        """Check admin password. Returns True when correct."""
        if password is None:
            return False
        return password == ADMIN_PASSWORD

    def reset_database(self, admin_password: str) -> bool:
        """Drop and recreate the users table. Requires admin password."""
        if not self._check_admin(admin_password):
            raise PermissionError("Invalid admin password")
        with self._conn:
            self._conn.execute("DROP TABLE IF EXISTS users")
            self._conn.execute("DROP TABLE IF EXISTS password_reset_tokens")
            self._conn.execute(
                """
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    salt TEXT NOT NULL,
                    pwd_hash TEXT NOT NULL,
                    email TEXT
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE password_reset_tokens (
                    id INTEGER PRIMARY KEY,
                    username TEXT NOT NULL,
                    token TEXT UNIQUE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (username) REFERENCES users (username)
                )
                """
            )
        self._conn.commit()
        return True

    def delete_user(self, username: str, admin_password: str) -> bool:
        """Delete a user by username. Requires admin password."""
        if not self._check_admin(admin_password):
            raise PermissionError("Invalid admin password")
        with self._conn:
            cur = self._conn.execute("DELETE FROM users WHERE username = ?", (username.strip(),))
        return cur.rowcount > 0

    def change_user_email(self, username: str, new_email: str, admin_password: str) -> bool:
        """Change a user's email. Requires admin password."""
        if not self._check_admin(admin_password):
            raise PermissionError("Invalid admin password")
        with self._conn:
            cur = self._conn.execute("UPDATE users SET email = ? WHERE username = ?", (new_email.strip(), username.strip()))
        return cur.rowcount > 0

    def verify_user(self, username: str, password: str) -> bool:
        cur = self._conn.cursor()
        cur.execute("SELECT salt, pwd_hash FROM users WHERE username = ?", (username.strip(),))
        row = cur.fetchone()
        if not row:
            return False
        salt, stored_hash = row
        return self._hash_password(password, salt) == stored_hash

    def username_exists(self, username: str) -> bool:
        cur = self._conn.cursor()
        cur.execute("SELECT 1 FROM users WHERE username = ?", (username.strip(),))
        return cur.fetchone() is not None

    def email_exists(self, email: str) -> bool:
        if not email:
            return False
        cur = self._conn.cursor()
        cur.execute("SELECT 1 FROM users WHERE email = ?", (email.strip(),))
        return cur.fetchone() is not None

    def ensure_admin(self, username: str = "admin", password: str = "secret", email: str = "admin@example.com") -> None:
        if not self.username_exists(username):
            self.create_user(username, password, email)

    # --- Password Reset Token Management ------------------------------------------------
    def generate_reset_token(self, username: str) -> Optional[str]:
        """Generate a password reset token for a user. Returns token or None."""
        if not self.username_exists(username):
            return None
        token = secrets.token_urlsafe(32)
        try:
            with self._conn:
                self._conn.execute(
                    "INSERT INTO password_reset_tokens (username, token) VALUES (?, ?)",
                    (username, token)
                )
            return token
        except sqlite3.IntegrityError:
            return None

    def verify_reset_token(self, token: str) -> Optional[str]:
        """Verify a reset token and return the username if valid, else None."""
        cur = self._conn.cursor()
        cur.execute("SELECT username FROM password_reset_tokens WHERE token = ?", (token,))
        row = cur.fetchone()
        return row[0] if row else None

    def reset_password_with_token(self, token: str, new_password: str) -> bool:
        """Reset a user's password using a valid token. Returns True on success."""
        username = self.verify_reset_token(token)
        if not username:
            return False
        salt = secrets.token_hex(16)
        pwd_hash = self._hash_password(new_password, salt)
        try:
            with self._conn:
                self._conn.execute(
                    "UPDATE users SET salt = ?, pwd_hash = ? WHERE username = ?",
                    (salt, pwd_hash, username)
                )
                self._conn.execute("DELETE FROM password_reset_tokens WHERE token = ?", (token,))
            return True
        except sqlite3.Error:
            return False

    def get_user_by_email(self, email: str) -> Optional[str]:
        """Get username by email. Returns username or None."""
        cur = self._conn.cursor()
        cur.execute("SELECT username FROM users WHERE email = ?", (email.strip(),))
        row = cur.fetchone()
        return row[0] if row else None

    def close(self) -> None:
        self._conn.close()
