import sqlite3
import hashlib
import secrets
import hmac
import getpass

DB_NAME = "library.db"


# ==========================================
# HASH PASSWORD
# ==========================================

def hash_password(password, salt):
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        600000
    )


# ==========================================
# CREATE ADMIN TABLE
# ==========================================

def create_admin_table():
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                username TEXT PRIMARY KEY,
                salt BLOB NOT NULL,
                password_hash BLOB NOT NULL
            )
        """)


# ==========================================
# CREATE ADMIN USING TERMINAL
# ==========================================

def create_admin():
    create_admin_table()

    with sqlite3.connect(DB_NAME) as conn:

        count = conn.execute(
            "SELECT COUNT(*) FROM admins"
        ).fetchone()[0]

        if count > 0:
            print("Admin account already exists.")
            return

        print("Create your admin account")

        username = input("Enter admin username: ").strip()
        password = getpass.getpass("Enter password: ")

        if not username or len(password) < 12:
            print(
                "Username is required and password "
                "must have at least 12 characters."
            )
            return

        salt = secrets.token_bytes(16)
        password_hash = hash_password(password, salt)

        conn.execute(
            """
            INSERT INTO admins (username, salt, password_hash)
            VALUES (?, ?, ?)
            """,
            (username, salt, password_hash)
        )

        print("Admin created successfully!")


# ==========================================
# INITIALIZE ADMIN FOR STREAMLIT CLOUD
# ==========================================

def initialize_admin(username, password):

    username = username.strip()

    if not username or len(password) < 12:
        raise ValueError(
            "Admin username is required and "
            "password must contain at least 12 characters."
        )

    create_admin_table()

    with sqlite3.connect(DB_NAME) as conn:

        existing = conn.execute(
            "SELECT username FROM admins WHERE username=?",
            (username,)
        ).fetchone()

        if existing is None:

            salt = secrets.token_bytes(16)
            password_hash = hash_password(password, salt)

            conn.execute(
                """
                INSERT INTO admins (username, salt, password_hash)
                VALUES (?, ?, ?)
                """,
                (username, salt, password_hash)
            )


# ==========================================
# CHECK LIBRARIAN LOGIN
# ==========================================

def check_login(username, password):

    create_admin_table()

    with sqlite3.connect(DB_NAME) as conn:

        result = conn.execute(
            """
            SELECT salt, password_hash
            FROM admins
            WHERE username=?
            """,
            (username.strip(),)
        ).fetchone()

    if result is None:
        return False

    salt, stored_hash = result

    entered_hash = hash_password(password, salt)

    return hmac.compare_digest(
        entered_hash,
        stored_hash
    )


# ==========================================
# RUN DIRECTLY
# ==========================================

if __name__ == "__main__":
    create_admin()