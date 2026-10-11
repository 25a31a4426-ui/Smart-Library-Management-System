# 📚 Smart Library Management System

A Smart Library Management System developed using Python,
Streamlit, and SQLite.

## Features

### Librarian
- Secure librarian login
- Register students
- Add, update, and delete books
- Issue and return books
- Manage book requests
- Generate and scan QR codes
- View library statistics

### Student
- Secure student login
- View available books
- Search books
- Smart book recommendations
- Request books
- View borrowed books
- Due date reminders
- Update password

## Technologies Used

- Python
- Streamlit
- SQLite
- Pandas
- Matplotlib
- OpenCV
- QR Code

## Installation

1. Clone the repository.
2. Install dependencies:

   pip install -r requirements.txt

3. Create an administrator account:

   python auth.py

4. Run the application:

   python -m streamlit run app.py

## Security

- Passwords are stored as salted hashes.
- Database files are excluded from GitHub.
- Sensitive files are protected using `.gitignore`.

## Developer

Developed as a Python project.