import sqlite3
import hashlib
import secrets
import hmac
import getpass

DB_NAME = "library.db"


def hash_password(password, salt):
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        600000
    )


def create_admin():
    conn = sqlite3.connect(DB_NAME)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            username TEXT PRIMARY KEY,
            salt BLOB NOT NULL,
            password_hash BLOB NOT NULL
        )
    """)

    conn.commit()

    count = conn.execute(
        "SELECT COUNT(*) FROM admins"
    ).fetchone()[0]

    if count == 0:
        print("Create your admin account")

        username = input("Enter admin username: ").strip()
        password = getpass.getpass("Enter password: ")

        if not username or len(password) < 12:
            print("Username required and password must have at least 12 characters.")
            conn.close()
            return

        salt = secrets.token_bytes(16)
        password_hash = hash_password(password, salt)

        conn.execute(
            "INSERT INTO admins VALUES (?, ?, ?)",
            (username, salt, password_hash)
        )

        conn.commit()
        print("Admin created successfully!")

    else:
        print("Admin account already exists.")

    conn.close()


def check_login(username, password):
    conn = sqlite3.connect(DB_NAME)

    result = conn.execute(
        "SELECT salt, password_hash FROM admins WHERE username=?",
        (username,)
    ).fetchone()

    conn.close()

    if result:
        salt, stored_hash = result
        entered_hash = hash_password(password, salt)

        return hmac.compare_digest(
            entered_hash,
            stored_hash
        )

    return False


if __name__ == "__main__":
    create_admin()