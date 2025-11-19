"""
User database abstraction using sqlite3.
Provides simple functions for creating users and verifying credentials.
Implements a safe password hashing using pbkdf2_hmac with salt.
"""
from __future__ import annotations
import sqlite3
from pathlib import Path
import hashlib
import secrets
from typing import Optional

DEFAULT_DB = Path(__file__).with_suffix(".db")


class UserDatabase:
    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = Path(db_path) if db_path else DEFAULT_DB
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

    def close(self) -> None:
        self._conn.close()