from flask import Flask, request, redirect
import sqlite3, uuid, qrcode, base64
from io import BytesIO
from datetime import datetime

app = Flask(__name__)

# ================= DATABASE =================
def db():
    return sqlite3.connect("attendance.db", check_same_thread=False)

def init_db():
    c = db().cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS lecturers(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT, username TEXT UNIQUE, password TEXT)""")

    c.execute("""CREATE TABLE IF NOT EXISTS students(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT, matric TEXT UNIQUE, fingerprint TEXT)""")

    c.execute("""CREATE TABLE IF NOT EXISTS sessions(
        id TEXT PRIMARY KEY, lecturer_id INTEGER, date TEXT)""")

    c.execute("""CREATE TABLE IF NOT EXISTS attendance(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT, matric TEXT, time TEXT)""")
    db().commit()

init_db()

# ================= UI =================
def page(title, body):
    return f"""
<html>
<head>
<title>{title}</title>
<style>
body{{font-family:Arial;background:#eef2f7}}
.box{{background:white;padding:20px;margin:30px auto;
width:420px;border-radius:10px;box-shadow:0 0 10px #ccc}}
input,button,select{{width:100%;padding:10px;margin:5px 0}}
button{{background:#007bff;color:white;border:none}}
table{{width:100%;border-collapse:collapse}}
th,td{{border:1px solid #ccc;padding:8px;text-align:center}}
a{{text-decoration:none}}
</style>
</head>
<body>
<div class="box">
<h2>{title}</h2>
{body}
<hr>
<a href="/">⬅ Home</a>
</div>
</body>
</html>
"""

# ================= HOME =================
@app.route("/")
def home():
    return page("Smart Attendance System", """
<a href="/lecturer-register"><button>Lecturer Registration </button></a>
<a href="/lecturer-login"><button>Lecturer Login & Generate QR</button></a>
<a href="/student-register"><button>Student Registration</button></a>
<a href="/mark"><button>Mark Attendance</button></a>
<a href="/report"><button>Attendance Report & Analytics</button></a>
""")

# ================= LECTURER =================
@app.route("/lecturer-register", methods=["GET","POST"])
def lecturer_register():
    if request.method=="POST":
        db().execute("INSERT INTO lecturers VALUES(NULL,?,?,?)",
        (request.form["name"],request.form["username"],request.form["password"]))
        db().commit()
        return redirect("/lecturer-login")
    return page("Lecturer Register", """
<form method="post">
<input name="name" placeholder="Full Name" required>
<input name="username" placeholder="Username" required>
<input name="password" placeholder="Password" required>
<button>Register</button>
</form>""")

@app.route("/lecturer-login", methods=["GET","POST"])
def lecturer_login():
    if request.method=="POST":
        cur=db().cursor()
        cur.execute("SELECT id FROM lecturers WHERE username=? AND password=?",
        (request.form["username"],request.form["password"]))
        lec=cur.fetchone()
        if lec:
            sid=str(uuid.uuid4())
            db().execute("INSERT INTO sessions VALUES(?,?,?)",
            (sid,lec[0],datetime.now().date().isoformat()))
            db().commit()

            qr=qrcode.make(sid)
            buf=BytesIO(); qr.save(buf)
            img=base64.b64encode(buf.getvalue()).decode()

            return page("QR Session Generated", f"""
<b>Session ID</b><br>{sid}<br><br>
<img src="data:image/png;base64,{img}">
""")
    return page("Lecturer Login", """
<form method="post">
<input name="username" placeholder="Username" required>
<input name="password" placeholder="Password" required>
<button>Login & Generate QR</button>
</form>""")

# ================= STUDENT =================
@app.route("/student-register", methods=["GET","POST"])
def student_register():
    if request.method=="POST":
        db().execute("INSERT INTO students VALUES(NULL,?,?,?)",
        (request.form["name"],request.form["matric"],request.form["fingerprint"]))
        db().commit()
        return redirect("/")
    return page("Student Register", """
<form method="post">
<input name="name" placeholder="Student Name" required>
<input name="matric" placeholder="Matric Number" required>
<input name="fingerprint" placeholder="Fingerprint ID (e.g FP001)" required>
<button>Register</button>
</form>""")

# ================= ATTENDANCE =================
@app.route("/mark", methods=["GET","POST"])
def mark():
    if request.method=="POST":
        s=request.form["session"]
        m=request.form["matric"]
        f=request.form["fingerprint"]

        cur=db().cursor()
        cur.execute("SELECT fingerprint FROM students WHERE matric=?", (m,))
        st=cur.fetchone()
        if not st or st[0]!=f:
            return page("Error","Invalid fingerprint")

        cur.execute("SELECT * FROM attendance WHERE session_id=? AND matric=?", (s,m))
        if cur.fetchone():
            return page("Error","Attendance already marked")

        db().execute("INSERT INTO attendance VALUES(NULL,?,?,?)",
        (s,m,datetime.now().strftime("%H:%M:%S")))
        db().commit()
        return page("Success","Attendance marked successfully")

    return page("Mark Attendance", """
<form method="post">
<input name="session" placeholder="QR Session ID" required>
<input name="matric" placeholder="Matric Number" required>
<input name="fingerprint" placeholder="Fingerprint ID" required>
<button>Submit</button>
</form>""")

# ================= REPORT & ANALYTICS =================
@app.route("/report", methods=["GET","POST"])
def report():
    cur=db().cursor()
    sessions=cur.execute("SELECT id FROM sessions").fetchall()
    q="SELECT * FROM attendance"
    data=cur.execute(q).fetchall()

    rows=""
    for r in data:
        rows+=f"<tr><td>{r[1]}</td><td>{r[2]}</td><td>{r[3]}</td></tr>"

    return page("Attendance Report & Analytics", f"""
<table>
<tr><th>Session</th><th>Matric</th><th>Time</th></tr>
{rows}
</table>
""")

# ================= RUN =================
if __name__=="__main__":
    app.run(debug=True)