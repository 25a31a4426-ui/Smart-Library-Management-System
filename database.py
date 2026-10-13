import sqlite3
import hashlib
import secrets
from datetime import date, timedelta


DB_NAME = "library.db"


def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ==========================================
# CREATE TABLES
# ==========================================

def create_table():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS books (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                author TEXT NOT NULL,
                quantity INTEGER NOT NULL
            )
        """)


def create_student_table():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                department TEXT NOT NULL,
                year INTEGER NOT NULL
            )
        """)


def create_issue_table():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS issued_books (
                issue_id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id INTEGER,
                student_id INTEGER,
                issue_date TEXT,
                due_date TEXT,
                return_date TEXT,
                fine INTEGER DEFAULT 0,
                FOREIGN KEY (book_id) REFERENCES books(id),
                FOREIGN KEY (student_id) REFERENCES students(id)
            )
        """)


def create_student_login_table():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS student_login (
                student_id INTEGER PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                FOREIGN KEY (student_id) REFERENCES students(id)
            )
        """)


def create_request_table():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS book_requests (
                request_id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id INTEGER NOT NULL,
                student_id INTEGER NOT NULL,
                request_date TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Pending',
                FOREIGN KEY (book_id) REFERENCES books(id),
                FOREIGN KEY (student_id) REFERENCES students(id)
            )
        """)


def create_admin_table():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                username TEXT PRIMARY KEY,
                salt BLOB NOT NULL,
                password_hash BLOB NOT NULL
            )
        """)


def initialize_database():
    create_table()
    create_student_table()
    create_issue_table()
    create_student_login_table()
    create_request_table()
    create_admin_table()


# ==========================================
# BOOK MANAGEMENT
# ==========================================

def add_book(title, author, quantity):
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO books (title, author, quantity) VALUES (?, ?, ?)",
            (title, author, quantity)
        )


def view_books():
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM books ORDER BY id DESC"
        ).fetchall()


def search_book(title):
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM books WHERE title LIKE ?",
            (f"%{title}%",)
        ).fetchall()


def update_book(book_id, title, author, quantity):
    with get_connection() as conn:
        cursor = conn.execute("""
            UPDATE books
            SET title=?, author=?, quantity=?
            WHERE id=?
        """, (title, author, quantity, book_id))

        return cursor.rowcount


def delete_book(book_id):
    with get_connection() as conn:
        # Preserve borrowing and request history.
        used = conn.execute("""
            SELECT 1 FROM issued_books WHERE book_id=?
            UNION
            SELECT 1 FROM book_requests WHERE book_id=?
        """, (book_id, book_id)).fetchone()

        if used:
            return 0

        cursor = conn.execute(
            "DELETE FROM books WHERE id=?",
            (book_id,)
        )

        return cursor.rowcount


# ==========================================
# STUDENT MANAGEMENT
# ==========================================

def add_student(name, department, year):
    with get_connection() as conn:
        cursor = conn.execute("""
            INSERT INTO students (name, department, year)
            VALUES (?, ?, ?)
        """, (name, department, year))

        return cursor.lastrowid


def view_students():
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM students ORDER BY id DESC"
        ).fetchall()


def get_student_profile(student_id):
    with get_connection() as conn:
        return conn.execute("""
            SELECT s.id, s.name, s.department, s.year, l.username
            FROM students s
            LEFT JOIN student_login l ON s.id = l.student_id
            WHERE s.id=?
        """, (student_id,)).fetchone()


# ==========================================
# PASSWORD SECURITY
# ==========================================

def hash_student_password(password, salt=None):
    if salt is None:
        salt = secrets.token_bytes(16)

    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        200000
    )

    return salt.hex() + ":" + password_hash.hex()


def verify_student_password(password, stored_password):
    try:
        salt_hex, hash_hex = stored_password.split(":")
        salt = bytes.fromhex(salt_hex)

        entered_hash = hash_student_password(password, salt)

        return secrets.compare_digest(
            entered_hash,
            stored_password
        )

    except (ValueError, TypeError):
        return False


def create_student_account(student_id, username, password):
    try:
        with get_connection() as conn:
            conn.execute("""
                INSERT INTO student_login
                (student_id, username, password)
                VALUES (?, ?, ?)
            """, (
                student_id,
                username,
                hash_student_password(password)
            ))

        return True

    except sqlite3.IntegrityError:
        return False


def register_student(name, department, year, username, password):
    """
    Register a student and create login credentials
    in one database transaction.
    """

    try:
        with get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO students (name, department, year)
                VALUES (?, ?, ?)
            """, (name, department, year))

            student_id = cursor.lastrowid

            conn.execute("""
                INSERT INTO student_login
                (student_id, username, password)
                VALUES (?, ?, ?)
            """, (
                student_id,
                username,
                hash_student_password(password)
            ))

        return student_id

    except sqlite3.IntegrityError:
        return None


def check_student_login(username, password):
    with get_connection() as conn:
        result = conn.execute("""
            SELECT student_id, password
            FROM student_login
            WHERE username=?
        """, (username,)).fetchone()

    if result is None:
        return None

    student_id, stored_password = result

    if verify_student_password(password, stored_password):
        return student_id

    return None


def change_student_password(student_id, old_password, new_password):
    with get_connection() as conn:
        result = conn.execute("""
            SELECT password
            FROM student_login
            WHERE student_id=?
        """, (student_id,)).fetchone()

        if result is None:
            return False

        if not verify_student_password(old_password, result[0]):
            return False

        conn.execute("""
            UPDATE student_login
            SET password=?
            WHERE student_id=?
        """, (
            hash_student_password(new_password),
            student_id
        ))

    return True


# ==========================================
# ISSUE AND RETURN BOOKS
# ==========================================

def issue_book(book_id, student_id):
    conn = get_connection()

    try:
        conn.execute("BEGIN IMMEDIATE")

        book = conn.execute(
            "SELECT quantity FROM books WHERE id=?",
            (book_id,)
        ).fetchone()

        if book is None:
            return "Book not found!"

        if book[0] <= 0:
            return "Book is not available!"

        student = conn.execute(
            "SELECT id FROM students WHERE id=?",
            (student_id,)
        ).fetchone()

        if student is None:
            return "Student not found!"

        today = date.today()
        due = today + timedelta(days=14)

        conn.execute("""
            INSERT INTO issued_books
            (book_id, student_id, issue_date, due_date)
            VALUES (?, ?, ?, ?)
        """, (
            book_id,
            student_id,
            today.isoformat(),
            due.isoformat()
        ))

        conn.execute("""
            UPDATE books
            SET quantity=quantity-1
            WHERE id=?
        """, (book_id,))

        conn.commit()

        return "Book issued successfully!"

    finally:
        conn.close()


def view_issued_books():
    with get_connection() as conn:
        return conn.execute("""
            SELECT
                i.issue_id,
                b.title,
                s.name,
                i.issue_date,
                i.due_date,
                i.return_date,
                i.fine
            FROM issued_books i
            JOIN books b ON i.book_id=b.id
            JOIN students s ON i.student_id=s.id
            ORDER BY i.issue_id DESC
        """).fetchall()


def return_book(issue_id):
    conn = get_connection()

    try:
        conn.execute("BEGIN IMMEDIATE")

        record = conn.execute("""
            SELECT book_id, due_date
            FROM issued_books
            WHERE issue_id=? AND return_date IS NULL
        """, (issue_id,)).fetchone()

        if record is None:
            return "Issue ID not found or already returned!"

        book_id, due_date = record

        today = date.today()
        due = date.fromisoformat(due_date)

        late_days = max(0, (today - due).days)
        fine = late_days * 5

        conn.execute("""
            UPDATE issued_books
            SET return_date=?, fine=?
            WHERE issue_id=?
        """, (
            today.isoformat(),
            fine,
            issue_id
        ))

        conn.execute("""
            UPDATE books
            SET quantity=quantity+1
            WHERE id=?
        """, (book_id,))

        conn.commit()

        return f"Book returned successfully! Fine: ₹{fine}"

    finally:
        conn.close()


def view_student_books(student_id):
    with get_connection() as conn:
        return conn.execute("""
            SELECT
                b.title,
                i.issue_date,
                i.due_date,
                i.return_date,
                i.fine
            FROM issued_books i
            JOIN books b ON i.book_id=b.id
            WHERE i.student_id=?
            ORDER BY i.issue_id DESC
        """, (student_id,)).fetchall()


# ==========================================
# BOOK REQUESTS
# ==========================================

def request_book(book_id, student_id):
    with get_connection() as conn:
        book = conn.execute("""
            SELECT quantity
            FROM books
            WHERE id=?
        """, (book_id,)).fetchone()

        if book is None:
            return "Book not found!"

        if book[0] <= 0:
            return "Book is currently unavailable!"

        existing = conn.execute("""
            SELECT request_id
            FROM book_requests
            WHERE book_id=?
              AND student_id=?
              AND status='Pending'
        """, (book_id, student_id)).fetchone()

        if existing:
            return "You already have a pending request for this book!"

        conn.execute("""
            INSERT INTO book_requests
            (book_id, student_id, request_date, status)
            VALUES (?, ?, ?, 'Pending')
        """, (
            book_id,
            student_id,
            date.today().isoformat()
        ))

    return "Book request submitted successfully!"


def view_book_requests():
    with get_connection() as conn:
        return conn.execute("""
            SELECT
                r.request_id,
                b.title,
                s.name,
                r.request_date,
                r.status
            FROM book_requests r
            JOIN books b ON r.book_id=b.id
            JOIN students s ON r.student_id=s.id
            ORDER BY r.request_id DESC
        """).fetchall()


def view_my_requests(student_id):
    with get_connection() as conn:
        return conn.execute("""
            SELECT
                b.title,
                r.request_date,
                r.status
            FROM book_requests r
            JOIN books b ON r.book_id=b.id
            WHERE r.student_id=?
            ORDER BY r.request_id DESC
        """, (student_id,)).fetchall()


def process_book_request(request_id, action):
    if action not in ("Approved", "Rejected"):
        return "Invalid action!"

    conn = get_connection()

    try:
        conn.execute("BEGIN IMMEDIATE")

        request = conn.execute("""
            SELECT book_id, student_id, status
            FROM book_requests
            WHERE request_id=?
        """, (request_id,)).fetchone()

        if request is None:
            return "Request not found!"

        book_id, student_id, status = request

        if status != "Pending":
            return "This request has already been processed!"

        if action == "Approved":
            book = conn.execute("""
                SELECT quantity
                FROM books
                WHERE id=?
            """, (book_id,)).fetchone()

            if book is None or book[0] <= 0:
                return "Book is no longer available!"

            today = date.today()
            due = today + timedelta(days=14)

            # Approving a request also issues the book.
            conn.execute("""
                INSERT INTO issued_books
                (book_id, student_id, issue_date, due_date)
                VALUES (?, ?, ?, ?)
            """, (
                book_id,
                student_id,
                today.isoformat(),
                due.isoformat()
            ))

            conn.execute("""
                UPDATE books
                SET quantity=quantity-1
                WHERE id=?
            """, (book_id,))

        conn.execute("""
            UPDATE book_requests
            SET status=?
            WHERE request_id=?
        """, (action, request_id))

        conn.commit()

        if action == "Approved":
            return "Request approved and book issued successfully!"

        return "Request rejected successfully!"

    finally:
        conn.close()