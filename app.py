from flask import Flask, request, redirect
import sqlite3
import uuid
import qrcode
import base64
from io import BytesIO
from datetime import datetime

app = Flask(__name__)

# ================= DATABASE =================
def get_db():
    return sqlite3.connect("attendance.db")

def init_db():
    db = get_db()
    c = db.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS lecturers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        username TEXT UNIQUE,
        password TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        matric TEXT UNIQUE,
        fingerprint TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        id TEXT PRIMARY KEY,
        lecturer_id INTEGER,
        created_at TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT,
        matric TEXT,
        time TEXT
    )
    """)

    db.commit()
    db.close()

init_db()

# ================= UI WRAPPER =================
def page(title, body):
    return f"""
    <html>
    <head>
        <title>{title}</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{
                font-family: Arial;
                background:#eef2f5;
                padding:20px;
            }}
            .box {{
                background:white;
                padding:20px;
                max-width:600px;
                margin:auto;
                border-radius:12px;
                box-shadow:0 4px 10px rgba(0,0,0,0.1);
            }}
            h2 {{ text-align:center; }}
            input, button {{
                width:100%;
                padding:12px;
                margin:8px 0;
                border-radius:6px;
                border:1px solid #ccc;
            }}
            button {{
                background:#007bff;
                color:grey;
                border:none;
                font-size:16px;
            }}
            table {{
                width:100%;
                border-collapse:collapse;
                margin-top:15px;
            }}
            th, td {{
                padding:10px;
                border:1px solid #ddd;
                text-align:center;
            }}
            th {{
                background:#007bff;
                color:white;
            }}
            a {{
                text-decoration:none;
            }}
        </style>
    </head>
    <body>
        <div class="box">
            <h2>{title}</h2>
            {body}
            <hr>
            <a href="/"><button>Home</button></a>
        </div>
    </body>
    </html>
    """

# ================= HOME =================
@app.route("/")
def home():
    return page("Smart Attendance System For C.U.S.T.E.C.H", """
        <a href="/lecturer-register"><button>Lecturer Registration</button></a>
        <a href="/lecturer-login"><button>Lecturer Login (Generate QR)</button></a>
        <a href="/student-register"><button>Student Registration</button></a>
        <a href="/mark-attendance"><button>Mark Attendance</button></a>
        <a href="/report"><button>Students Attendance Report</button></a>
    """)

# ================= LECTURER REGISTER =================
@app.route("/lecturer-register", methods=["GET", "POST"])
def lecturer_register():
    if request.method == "POST":
        db = get_db()
        db.execute(
            "INSERT INTO lecturers (name, username, password) VALUES (?, ?, ?)",
            (request.form["name"], request.form["username"], request.form["password"])
        )
        db.commit()
        db.close()
        return redirect("/lecturer-login")

    return page("Lecturer Registration", """
        <form method="post">
            <input name="name" placeholder="Full Name" required>
            <input name="username" placeholder="Username" required>
            <input name="password" placeholder="Password" required>
            <button>Register</button>
        </form>
    """)

# ================= LECTURER LOGIN + QR =================
@app.route("/lecturer-login", methods=["GET", "POST"])
def lecturer_login():
    if request.method == "POST":
        db = get_db()
        c = db.cursor()
        c.execute(
            "SELECT id FROM lecturers WHERE username=? AND password=?",
            (request.form["username"], request.form["password"])
        )
        lecturer = c.fetchone()
        db.close()

        if not lecturer:
            return page("Error", "Invalid login details")

        session_id = str(uuid.uuid4())

        db = get_db()
        db.execute(
            "INSERT INTO sessions VALUES (?, ?, ?)",
            (session_id, lecturer[0], datetime.now().isoformat())
        )
        db.commit()
        db.close()

        qr = qrcode.make(session_id)
        buf = BytesIO()
        qr.save(buf)
        qr_b64 = base64.b64encode(buf.getvalue()).decode()

        return page("QR Attendance Session", f"""
            <p><b>Session ID:</b></p>
            <p>{session_id}</p>
            <img src="data:image/png;base64,{qr_b64}" width="250">
            <p>Students should scan this QR and submit their fingerprint.</p>
        """)

    return page("Lecturer Login", """
        <form method="post">
            <input name="username" placeholder="Username" required>
            <input name="password" placeholder="Password" required>
            <button>Login & Generate QR</button>
        </form>
    """)

# ================= STUDENT REGISTER =================
@app.route("/student-register", methods=["GET", "POST"])
def student_register():
    if request.method == "POST":
        db = get_db()
        db.execute(
            "INSERT INTO students (name, matric, fingerprint) VALUES (?, ?, ?)",
            (request.form["name"], request.form["matric"], request.form["fingerprint"])
        )
        db.commit()
        db.close()
        return redirect("/")

    return page("Student Registration", """
        <form method="post">
            <input name="name" placeholder="Student Name" required>
            <input name="matric" placeholder="Matric Number" required>
            <input name="fingerprint" placeholder="Fingerprint ID (e.g FP1023)" required>
            <button>Register</button>
        </form>
    """)

# ================= MARK ATTENDANCE =================
@app.route("/mark-attendance", methods=["GET", "POST"])
def mark_attendance():
    if request.method == "POST":
        session_id = request.form["session"]
        matric = request.form["matric"]
        fingerprint = request.form["fingerprint"]

        db = get_db()
        c = db.cursor()

        c.execute("SELECT fingerprint FROM students WHERE matric=?", (matric,))
        student = c.fetchone()

        if not student or student[0] != fingerprint:
            return page("Error", "Invalid student or fingerprint")

        c.execute(
            "SELECT * FROM attendance WHERE session_id=? AND matric=?",
            (session_id, matric)
        )
        if c.fetchone():
            return page("Error", "Attendance already marked")

        c.execute(
            "INSERT INTO attendance (session_id, matric, time) VALUES (?, ?, ?)",
            (session_id, matric, datetime.now().isoformat())
        )
        db.commit()
        db.close()

        return page("Success", "Attendance marked successfully")

    return page("Mark Attendance", """
        <form method="post">
            <input name="session" placeholder="QR Session ID" required>
            <input name="matric" placeholder="Matric Number" required>
            <input name="fingerprint" placeholder="Fingerprint ID" required>
            <button>Submit Attendance</button>
        </form>
    """)

# ================= REPORT =================
@app.route("/report")
def report():
    db = get_db()
    rows = db.execute("""
        SELECT attendance.session_id, students.name, attendance.matric, attendance.time
        FROM attendance
        JOIN students ON students.matric = attendance.matric
        ORDER BY attendance.time DESC
    """).fetchall()
    db.close()

    table = """
    <table>
        <tr>
            <th>Session</th>
            <th>Student Name</th>
            <th>Matric</th>
            <th>Time</th>
        </tr>
    """

    for r in rows:
        table += f"""
        <tr>
            <td>{r[0][:8]}...</td>
            <td>{r[1]}</td>
            <td>{r[2]}</td>
            <td>{r[3]}</td>
        </tr>
        """

    table += "</table>"

    return page("Final Attendance Report", table)

# ================= RUN =================
if __name__ == "__main__":
    app.run(debug=True)