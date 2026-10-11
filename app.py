import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import qrcode
import cv2
import numpy as np
import sqlite3

from io import BytesIO
from datetime import date

from auth import check_login

from database import (
    initialize_database,
    add_book,
    view_books,
    search_book,
    update_book,
    delete_book,
    view_students,
    register_student,
    check_student_login,
    get_student_profile,
    change_student_password,
    issue_book,
    return_book,
    view_issued_books,
    view_student_books,
    request_book,
    view_book_requests,
    view_my_requests,
    process_book_request
)


# ==========================================
# PAGE SETTINGS
# ==========================================

st.set_page_config(
    page_title="Smart Library Management System",
    page_icon="📚",
    layout="wide"
)


# ==========================================
# LOAD CSS
# ==========================================

try:
    with open("style.css", encoding="utf-8") as file:
        st.markdown(
            f"<style>{file.read()}</style>",
            unsafe_allow_html=True
        )
except FileNotFoundError:
    pass


# ==========================================
# INITIALIZE DATABASE
# ==========================================

initialize_database()


# ==========================================
# SESSION STATE
# ==========================================

if "role" not in st.session_state:
    st.session_state.role = None

if "student_id" not in st.session_state:
    st.session_state.student_id = None


# ==========================================
# COMMON FUNCTIONS
# ==========================================

def show_books(books):
    if books:
        df = pd.DataFrame(
            books,
            columns=[
                "Book ID",
                "Title",
                "Author",
                "Available Copies"
            ]
        )

        st.dataframe(
            df,
            use_container_width=True
        )
    else:
        st.info("No books found.")


# ==========================================
# SMART BOOK RECOMMENDATIONS
# ==========================================

def show_recommendations():

    st.title("🤖 Smart Book Recommendations")

    categories = {
        "Programming": [
            "python", "java", "c++", "programming",
            "coding", "javascript", "data structures"
        ],
        "Database": [
            "database", "sql", "dbms", "mysql",
            "mongodb"
        ],
        "Artificial Intelligence": [
            "artificial intelligence", "machine learning",
            "deep learning", "neural", "ai"
        ],
        "Data Science": [
            "data science", "pandas", "numpy",
            "statistics", "data analysis"
        ],
        "Networking": [
            "network", "networking", "cybersecurity",
            "internet", "security"
        ],
        "Web Development": [
            "html", "css", "javascript", "react",
            "web development"
        ],
        "Mathematics": [
            "mathematics", "maths", "algebra",
            "calculus", "probability"
        ]
    }

    interest = st.selectbox(
        "Select Your Interest",
        list(categories.keys())
    )

    if st.button("Get Recommendations"):

        books = view_books()
        keywords = categories[interest]

        conn = sqlite3.connect("library.db")

        try:
            rows = conn.execute("""
                SELECT book_id, COUNT(*)
                FROM issued_books
                GROUP BY book_id
            """).fetchall()

            popularity = dict(rows)

            borrowed_ids = set()

            if st.session_state.role == "Student":
                student_id = st.session_state.student_id

                history = conn.execute("""
                    SELECT DISTINCT book_id
                    FROM issued_books
                    WHERE student_id=?
                """, (student_id,)).fetchall()

                borrowed_ids = {row[0] for row in history}

        finally:
            conn.close()

        recommendations = []

        for book in books:

            book_id, title, author, quantity = book

            if quantity <= 0:
                continue

            title_lower = title.lower()

            # Only recommend books matching the selected topic.
            if not any(word in title_lower for word in keywords):
                continue

            score = 10

            # Frequently borrowed books receive a higher ranking.
            score += popularity.get(book_id, 0) * 2

            # Prefer books the student has not borrowed before.
            if book_id in borrowed_ids:
                score -= 5

            recommendations.append(
                (score, book)
            )

        recommendations.sort(
            key=lambda item: item[0],
            reverse=True
        )

        if recommendations:

            st.success("Recommended Books")

            show_books([
                item[1] for item in recommendations
            ])

        else:
            st.warning(
                "No matching available books found."
            )


# ==========================================
# GENERATE QR CODE
# ==========================================

def show_qr_generator():

    st.title("📷 Generate Book QR Code")

    books = view_books()

    if not books:
        st.warning("No books available.")
        return

    options = {
        f"{b[0]} - {b[1]}": b
        for b in books
    }

    selected = st.selectbox(
        "Select Book",
        list(options.keys())
    )

    book = options[selected]

    if st.button("Generate QR Code"):

        qr = qrcode.make(
            f"BOOK_ID:{book[0]}"
        )

        buffer = BytesIO()
        qr.save(buffer, format="PNG")

        st.session_state.qr_image = buffer.getvalue()
        st.session_state.qr_book_id = book[0]

    if (
        st.session_state.get("qr_book_id") == book[0]
        and "qr_image" in st.session_state
    ):

        st.image(
            st.session_state.qr_image,
            width=250
        )

        st.download_button(
            "Download QR Code",
            data=st.session_state.qr_image,
            file_name=f"book_{book[0]}.png",
            mime="image/png"
        )


# ==========================================
# SCAN QR CODE
# ==========================================

def show_qr_scanner():

    st.title("📱 Scan Book QR Code")

    method = st.radio(
        "Scanning Method",
        ["Camera", "Upload Image"]
    )

    if method == "Camera":
        image_file = st.camera_input(
            "Capture QR Code"
        )
    else:
        image_file = st.file_uploader(
            "Upload QR Code",
            type=["png", "jpg", "jpeg"]
        )

    if image_file is None:
        return

    image_bytes = np.frombuffer(
        image_file.getvalue(),
        dtype=np.uint8
    )

    image = cv2.imdecode(
        image_bytes,
        cv2.IMREAD_COLOR
    )

    if image is None:
        st.error("Invalid image.")
        return

    detector = cv2.QRCodeDetector()

    data, _, _ = detector.detectAndDecode(image)

    if not data.startswith("BOOK_ID:"):
        st.error("No valid book QR code detected.")
        return

    try:
        book_id = int(data.split(":", 1)[1])
    except ValueError:
        st.error("Invalid QR code.")
        return

    book = next(
        (b for b in view_books() if b[0] == book_id),
        None
    )

    if book:

        st.success("Book Found!")

        st.write("**Book ID:**", book[0])
        st.write("**Title:**", book[1])
        st.write("**Author:**", book[2])
        st.write("**Available Copies:**", book[3])

    else:
        st.warning("Book not found.")


# ==========================================
# LOGIN PAGE
# ==========================================

if st.session_state.role is None:

    st.title("📚 Smart Library Management System")

    st.subheader("Login")

    login_type = st.radio(
        "Select Login Type",
        ["Librarian", "Student"],
        horizontal=True
    )

    with st.form("login_form"):

        username = st.text_input("Username")

        password = st.text_input(
            "Password",
            type="password"
        )

        login = st.form_submit_button("Login")

        if login:

            if login_type == "Librarian":

                if check_login(username, password):

                    st.session_state.role = "Librarian"
                    st.session_state.student_id = None

                    st.rerun()

                else:
                    st.error("Invalid librarian login.")

            else:

                student_id = check_student_login(
                    username.strip(),
                    password
                )

                if student_id is not None:

                    st.session_state.role = "Student"
                    st.session_state.student_id = student_id

                    st.rerun()

                else:
                    st.error("Invalid student username or password.")

    st.stop()


# ==========================================
# SIDEBAR
# ==========================================

role = st.session_state.role

st.sidebar.title("📚 Smart Library")

st.sidebar.write(
    f"Logged in as: **{role}**"
)

if role == "Librarian":

    menu_options = [
        "Home",
        "Register Student",
        "View Students",
        "Add Book",
        "View Books",
        "Search Book",
        "Generate QR Code",
        "Scan QR Code",
        "Smart Recommendations",
        "Issue Book",
        "Return Book",
        "Issued Books",
        "Manage Book Requests",
        "Update Book",
        "Delete Book"
    ]

else:

    menu_options = [
        "Home",
        "My Profile",
        "View Books",
        "Search Book",
        "Smart Recommendations",
        "Scan QR Code",
        "Request a Book",
        "My Book Requests",
        "My Borrowed Books",
        "Due Date Reminders"
    ]

menu = st.sidebar.selectbox(
    "Select Menu",
    menu_options
)

st.sidebar.divider()

if st.sidebar.button("🚪 Logout"):

    st.session_state.role = None
    st.session_state.student_id = None

    st.session_state.pop("qr_image", None)
    st.session_state.pop("qr_book_id", None)

    st.rerun()


# ==========================================
# HOME
# ==========================================

if menu == "Home":

    if role == "Librarian":

        st.title("Library Dashboard")

        books = view_books()
        students = view_students()
        issued = view_issued_books()
        requests = view_book_requests()

        available = sum(b[3] for b in books)

        active = [
            i for i in issued
            if i[5] is None
        ]

        pending = [
            r for r in requests
            if r[4] == "Pending"
        ]

        col1, col2, col3, col4 = st.columns(4)

        col1.metric("📚 Available Books", available)
        col2.metric("📤 Issued Books", len(active))
        col3.metric("👨‍🎓 Students", len(students))
        col4.metric("📩 Pending Requests", len(pending))

        st.divider()

        st.subheader("📊 Library Statistics")

        fig, ax = plt.subplots(figsize=(7, 4))

        ax.bar(
            ["Available", "Issued", "Requests"],
            [available, len(active), len(pending)],
            color="#7B4DDB"
        )

        ax.set_ylabel("Count")

        st.pyplot(fig)
        plt.close(fig)

        st.subheader("Recent Transactions")

        if issued:
            df = pd.DataFrame(
                issued,
                columns=[
                    "Issue ID", "Book", "Student",
                    "Issue Date", "Due Date",
                    "Return Date", "Fine"
                ]
            )

            st.dataframe(
                df.head(5),
                use_container_width=True
            )
        else:
            st.info("No transactions yet.")

    else:

        st.title("👨‍🎓 Student Dashboard")

        student_id = st.session_state.student_id

        profile = get_student_profile(student_id)

        if profile:
            st.write(f"Welcome, **{profile[1]}**!")

        records = view_student_books(student_id)

        active = [
            r for r in records
            if r[3] is None
        ]

        overdue = [
            r for r in active
            if date.fromisoformat(r[2]) < date.today()
        ]

        col1, col2, col3 = st.columns(3)

        col1.metric(
            "📚 Available Books",
            sum(b[3] for b in view_books())
        )

        col2.metric(
            "📖 My Borrowed Books",
            len(active)
        )

        col3.metric(
            "⏰ Overdue Books",
            len(overdue)
        )

        st.info(
            "Use the sidebar to request books, "
            "view recommendations, and check due dates."
        )


# ==========================================
# MY PROFILE - NEW
# ==========================================

elif menu == "My Profile" and role == "Student":

    st.title("👤 My Profile")

    student_id = st.session_state.student_id

    profile = get_student_profile(student_id)

    if profile:

        st.write("**Student ID:**", profile[0])
        st.write("**Name:**", profile[1])
        st.write("**Department:**", profile[2])
        st.write("**Year:**", profile[3])
        st.write("**Username:**", profile[4])

        st.write("**Password:** ********")

        st.divider()

        st.subheader("🔐 Change Password")

        with st.form("change_password_form"):

            old_password = st.text_input(
                "Current Password",
                type="password"
            )

            new_password = st.text_input(
                "New Password",
                type="password"
            )

            confirm_password = st.text_input(
                "Confirm New Password",
                type="password"
            )

            submit = st.form_submit_button(
                "Update Password"
            )

            if submit:

                if not old_password or not new_password:
                    st.warning("Please fill all fields.")

                elif len(new_password) < 8:
                    st.warning(
                        "New password must contain at least 8 characters."
                    )

                elif new_password != confirm_password:
                    st.error("New passwords do not match.")

                elif new_password == old_password:
                    st.warning(
                        "Choose a different new password."
                    )

                else:

                    success = change_student_password(
                        student_id,
                        old_password,
                        new_password
                    )

                    if success:
                        st.success(
                            "Password updated successfully!"
                        )
                    else:
                        st.error(
                            "Current password is incorrect."
                        )


# ==========================================
# REGISTER STUDENT
# ==========================================

elif menu == "Register Student" and role == "Librarian":

    st.title("👨‍🎓 Register Student")

    with st.form("register_student_form"):

        name = st.text_input("Student Name")
        department = st.text_input("Department")

        year = st.number_input(
            "Year",
            min_value=1,
            max_value=4,
            step=1
        )

        username = st.text_input("Username")

        password = st.text_input(
            "Password",
            type="password"
        )

        submit = st.form_submit_button(
            "Register Student"
        )

        if submit:

            if not all([
                name.strip(),
                department.strip(),
                username.strip(),
                password
            ]):

                st.warning("Please fill all fields.")

            elif len(password) < 8:

                st.warning(
                    "Password must contain at least 8 characters."
                )

            else:

                student_id = register_student(
                    name.strip(),
                    department.strip(),
                    int(year),
                    username.strip(),
                    password
                )

                if student_id is not None:

                    st.success(
                        "Student registered successfully!"
                    )

                    st.write("Student ID:", student_id)
                    st.write("Username:", username.strip())

                else:

                    st.error(
                        "Username already exists. "
                        "Please choose another username."
                    )


# ==========================================
# VIEW STUDENTS
# ==========================================

elif menu == "View Students" and role == "Librarian":

    st.title("👨‍🎓 Registered Students")

    students = view_students()

    if students:

        st.dataframe(
            pd.DataFrame(
                students,
                columns=[
                    "Student ID",
                    "Name",
                    "Department",
                    "Year"
                ]
            ),
            use_container_width=True
        )

    else:
        st.info("No students registered.")


# ==========================================
# ADD BOOK
# ==========================================

elif menu == "Add Book" and role == "Librarian":

    st.title("📚 Add Book")

    with st.form("add_book_form"):

        title = st.text_input("Book Title")
        author = st.text_input("Author")

        quantity = st.number_input(
            "Quantity",
            min_value=1,
            step=1
        )

        submit = st.form_submit_button("Add Book")

        if submit:

            if title.strip() and author.strip():

                add_book(
                    title.strip(),
                    author.strip(),
                    int(quantity)
                )

                st.success("Book added successfully!")

            else:
                st.warning("Please fill all fields.")


# ==========================================
# VIEW BOOKS
# ==========================================

elif menu == "View Books":

    st.title("📚 View Books")

    show_books(view_books())


# ==========================================
# SEARCH BOOK
# ==========================================

elif menu == "Search Book":

    st.title("🔍 Search Book")

    keyword = st.text_input("Enter Book Title")

    if st.button("Search"):

        if keyword.strip():
            show_books(search_book(keyword.strip()))
        else:
            st.warning("Enter a book title.")


# ==========================================
# QR CODE
# ==========================================

elif menu == "Generate QR Code" and role == "Librarian":

    show_qr_generator()


elif menu == "Scan QR Code":

    show_qr_scanner()


# ==========================================
# RECOMMENDATIONS
# ==========================================

elif menu == "Smart Recommendations":

    show_recommendations()


# ==========================================
# REQUEST A BOOK - NEW
# ==========================================

elif menu == "Request a Book" and role == "Student":

    st.title("📩 Request a Book")

    books = [
        b for b in view_books()
        if b[3] > 0
    ]

    if not books:

        st.warning("No books available.")

    else:

        options = {
            f"{b[0]} - {b[1]} (Available: {b[3]})": b
            for b in books
        }

        selected = st.selectbox(
            "Select Book",
            list(options.keys())
        )

        book = options[selected]

        st.write("**Title:**", book[1])
        st.write("**Author:**", book[2])
        st.write("**Available Copies:**", book[3])

        if st.button("Request Book"):

            result = request_book(
                book[0],
                st.session_state.student_id
            )

            if result == "Book request submitted successfully!":
                st.success(result)
            else:
                st.warning(result)


# ==========================================
# MY BOOK REQUESTS - NEW
# ==========================================

elif menu == "My Book Requests" and role == "Student":

    st.title("📋 My Book Requests")

    requests = view_my_requests(
        st.session_state.student_id
    )

    if requests:

        st.dataframe(
            pd.DataFrame(
                requests,
                columns=[
                    "Book",
                    "Request Date",
                    "Status"
                ]
            ),
            use_container_width=True
        )

    else:
        st.info("You have not requested any books.")


# ==========================================
# MANAGE BOOK REQUESTS - NEW
# ==========================================

elif menu == "Manage Book Requests" and role == "Librarian":

    st.title("📩 Manage Book Requests")

    requests = view_book_requests()

    if requests:

        df = pd.DataFrame(
            requests,
            columns=[
                "Request ID",
                "Book",
                "Student",
                "Request Date",
                "Status"
            ]
        )

        st.dataframe(
            df,
            use_container_width=True
        )

        pending = [
            r for r in requests
            if r[4] == "Pending"
        ]

        if pending:

            options = {
                f"Request {r[0]} - {r[1]} - {r[2]}": r[0]
                for r in pending
            }

            selected = st.selectbox(
                "Select Pending Request",
                list(options.keys())
            )

            request_id = options[selected]

            col1, col2 = st.columns(2)

            with col1:

                if st.button("✅ Approve Request"):

                    result = process_book_request(
                        request_id,
                        "Approved"
                    )

                    if result.startswith("Request approved"):
                        st.success(result)
                    else:
                        st.warning(result)

            with col2:

                if st.button("❌ Reject Request"):

                    result = process_book_request(
                        request_id,
                        "Rejected"
                    )

                    if result.startswith("Request rejected"):
                        st.success(result)
                    else:
                        st.warning(result)

        else:
            st.info("No pending requests.")

    else:
        st.info("No book requests yet.")


# ==========================================
# MY BORROWED BOOKS
# ==========================================

elif menu == "My Borrowed Books" and role == "Student":

    st.title("📖 My Borrowed Books")

    records = view_student_books(
        st.session_state.student_id
    )

    if records:

        rows = []

        for record in records:

            title, issue_date, due_date, return_date, fine = record

            if return_date is None:

                late_days = max(
                    0,
                    (date.today() - date.fromisoformat(due_date)).days
                )

                current_fine = late_days * 5
                status = "Borrowed"

            else:

                current_fine = fine
                status = "Returned"

            rows.append({
                "Book": title,
                "Issue Date": issue_date,
                "Due Date": due_date,
                "Return Date": return_date or "-",
                "Status": status,
                "Fine (₹)": current_fine
            })

        st.dataframe(
            pd.DataFrame(rows),
            use_container_width=True
        )

    else:
        st.info("No borrowed books found.")


# ==========================================
# DUE DATE REMINDERS - NEW
# ==========================================

elif menu == "Due Date Reminders" and role == "Student":

    st.title("📅 Due Date Reminders")

    records = view_student_books(
        st.session_state.student_id
    )

    active_books = [
        r for r in records
        if r[3] is None
    ]

    if not active_books:

        st.info("You have no books to return.")

    else:

        for record in active_books:

            title, issue_date, due_date, _, _ = record

            due = date.fromisoformat(due_date)

            days_left = (due - date.today()).days

            st.subheader(f"📖 {title}")

            st.write("**Issue Date:**", issue_date)
            st.write("**Due Date:**", due_date)

            if days_left < 0:

                fine = abs(days_left) * 5

                st.error(
                    f"⚠️ Overdue by {abs(days_left)} days! "
                    f"Current fine: ₹{fine}"
                )

            elif days_left == 0:

                st.warning("⚠️ Return this book today!")

            elif days_left <= 3:

                st.warning(
                    f"⏰ Only {days_left} days remaining!"
                )

            else:

                st.success(
                    f"✅ {days_left} days remaining."
                )

            st.divider()

        st.info(
            "Books must be returned within 14 days. "
            "Late fine: ₹5 per day."
        )


# ==========================================
# ISSUE BOOK
# ==========================================

elif menu == "Issue Book" and role == "Librarian":

    st.title("📤 Issue Book")

    books = [
        b for b in view_books()
        if b[3] > 0
    ]

    students = view_students()

    if not books:
        st.warning("No available books.")

    elif not students:
        st.warning("No registered students.")

    else:

        book_options = {
            f"{b[0]} - {b[1]}": b[0]
            for b in books
        }

        student_options = {
            f"{s[0]} - {s[1]}": s[0]
            for s in students
        }

        selected_book = st.selectbox(
            "Select Book",
            list(book_options.keys())
        )

        selected_student = st.selectbox(
            "Select Student",
            list(student_options.keys())
        )

        if st.button("Issue Book"):

            result = issue_book(
                book_options[selected_book],
                student_options[selected_student]
            )

            if result == "Book issued successfully!":
                st.success(result)
            else:
                st.warning(result)


# ==========================================
# RETURN BOOK
# ==========================================

elif menu == "Return Book" and role == "Librarian":

    st.title("📥 Return Book")

    issued = [
        i for i in view_issued_books()
        if i[5] is None
    ]

    if issued:

        options = {
            f"{i[0]} - {i[1]} - {i[2]}": i[0]
            for i in issued
        }

        selected = st.selectbox(
            "Select Issued Book",
            list(options.keys())
        )

        if st.button("Return Book"):

            result = return_book(
                options[selected]
            )

            if result.startswith("Book returned successfully"):
                st.success(result)
            else:
                st.warning(result)

    else:
        st.info("No active issued books.")


# ==========================================
# ISSUED BOOKS
# ==========================================

elif menu == "Issued Books" and role == "Librarian":

    st.title("📋 Issued Books")

    issued = view_issued_books()

    if issued:

        st.dataframe(
            pd.DataFrame(
                issued,
                columns=[
                    "Issue ID",
                    "Book",
                    "Student",
                    "Issue Date",
                    "Due Date",
                    "Return Date",
                    "Fine"
                ]
            ),
            use_container_width=True
        )

    else:
        st.info("No issued books found.")


# ==========================================
# UPDATE BOOK
# ==========================================

elif menu == "Update Book" and role == "Librarian":

    st.title("✏️ Update Book")

    books = view_books()

    if books:

        options = {
            f"{b[0]} - {b[1]}": b
            for b in books
        }

        selected = st.selectbox(
            "Select Book",
            list(options.keys())
        )

        book = options[selected]

        with st.form("update_book_form"):

            title = st.text_input(
                "Title",
                value=book[1]
            )

            author = st.text_input(
                "Author",
                value=book[2]
            )

            quantity = st.number_input(
                "Quantity",
                min_value=0,
                value=book[3],
                step=1
            )

            submit = st.form_submit_button(
                "Update Book"
            )

            if submit:

                if title.strip() and author.strip():

                    update_book(
                        book[0],
                        title.strip(),
                        author.strip(),
                        int(quantity)
                    )

                    st.success("Book updated successfully!")

                else:
                    st.warning("Please fill all fields.")

    else:
        st.info("No books available.")


# ==========================================
# DELETE BOOK
# ==========================================

elif menu == "Delete Book" and role == "Librarian":

    st.title("🗑️ Delete Book")

    books = view_books()

    if books:

        options = {
            f"{b[0]} - {b[1]}": b[0]
            for b in books
        }

        selected = st.selectbox(
            "Select Book",
            list(options.keys())
        )

        confirm = st.checkbox(
            "I confirm that I want to delete this book."
        )

        if st.button("Delete Book"):

            if not confirm:

                st.warning("Please confirm deletion.")

            else:

                result = delete_book(
                    options[selected]
                )

                if result:
                    st.success("Book deleted successfully!")
                else:
                    st.error(
                        "Cannot delete this book because it has "
                        "borrowing or request history."
                    )

    else:
        st.info("No books available.")