from flask import Flask, request, redirect, Response
import sqlite3, uuid, hashlib, base64, csv
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import qrcode
from io import BytesIO, StringIO

app = Flask(__name__)
DB = "attendance.db"

# ---------------- DATABASE ----------------
def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    con = db()
    cur = con.cursor()
    # Users table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        matric TEXT UNIQUE,
        password TEXT,
        role TEXT,
        fingerprint TEXT
    )
    """)
    # Sessions table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS sessions(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lecturer_id INTEGER,
        start_time TEXT,
        end_time TEXT,
        is_active INTEGER,
        qr_token TEXT
    )
    """)
    # Attendance table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS attendance(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER,
        session_id INTEGER,
        time TEXT,
        UNIQUE(student_id, session_id)
    )
    """)
    con.commit()
    con.close()

init_db()

# ---------------- HELPERS ----------------
def hash_fp(x): 
    return hashlib.sha256(x.encode()).hexdigest()

def close_expired():
    con = db()
    con.execute("UPDATE sessions SET is_active=0 WHERE end_time<=?", (datetime.now(),))
    con.commit()
    con.close()

def qr_image(data):
    img = qrcode.make(data)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()

# ---------------- UI ----------------
STYLE = """
<meta name=viewport content="width=device-width, initial-scale=1">
<style>
body{font-family:Arial;background:#eef;padding:15px}
.card{background:#fff;padding:20px;border-radius:12px;max-width:480px;margin:auto;margin-bottom:15px}
input,button{width:100%;padding:12px;margin:8px 0;border-radius:8px}
button{background:#0066ff;color:white;border:none;font-size:16px}
.end{background:red}
img{width:100%;margin:10px 0}
small{color:#555}
a{display:block;text-align:center;margin-top:10px}
table, th, td{border:1px solid #ccc;border-collapse:collapse;padding:8px;text-align:left;width:100%}
th{background:#f2f2f2}
h3{background:#ddd;padding:8px;border-radius:8px}
</style>
"""

# ---------------- LOGIN ----------------
@app.route("/", methods=["GET","POST"])
def login():
    msg=""
    if request.method=="POST":
        u,p=request.form["u"],request.form["p"]
        con=db();cur=con.cursor()
        cur.execute("SELECT * FROM users WHERE matric=?", (u,))
        user=cur.fetchone();con.close()
        if user and check_password_hash(user["password"],p):
            return redirect("/{}?id={}".format(user['role'], user['id']))
        msg="Invalid login"
    return """
    {style}<div class=card>
    <h2>Login</h2>
    <form method=post>
    <input name=u placeholder="Matric Number or Lecturer_id" required>
    <input name=p type=password placeholder="Password" required>
    <button>Login</button></form>
    <p>{msg}</p>
    <a href=/register_student>Student Registration</a>
    <a href=/register_lecturer>Lecturer Registration</a>
    </div>
    """.format(style=STYLE,msg=msg)

# ---------------- STUDENT REGISTRATION ----------------
@app.route("/register_student", methods=["GET","POST"])
def register_student():
    msg=""
    if request.method=="POST":
        try:
            con=db()
            con.execute("INSERT INTO users VALUES(NULL,?,?,?,?,?)",
            (
                request.form["name"],
                request.form["matric"],
                generate_password_hash(request.form["p"]),
                "student",
                hash_fp(request.form["fp"])
            ))
            con.commit();con.close()
            return redirect("/")
        except:
            msg="This matric Number already exists"
    return """
    {style}<div class=card>
    <h2>Student Registration</h2>
    <form method=post>
    <input name=name placeholder="Full Name" required>
    <input name=matric placeholder="Matric Number" required>
    <input name=p type=password placeholder="Password" required>
    <input name=fp placeholder="Fingerprint Code eg:FP1001" required>
    <button>Register</button></form>
    <p>{msg}</p></div>
    """.format(style=STYLE,msg=msg)

# ---------------- LECTURER REGISTRATION ----------------
@app.route("/register_lecturer", methods=["GET","POST"])
def register_lecturer():
    msg=""
    if request.method=="POST":
        try:
            con=db()
            con.execute("INSERT INTO users VALUES(NULL,?,?,?,?,NULL)",
            (
                request.form["name"],
                request.form["u"],
                generate_password_hash(request.form["p"]),
                "lecturer"
            ))
            con.commit();con.close()
            return redirect("/")
        except:
            msg="This username already exists"
    return """
    {style}<div class=card>
    <h2>Lecturer Registration</h2>
    <form method=post>
    <input name=name placeholder="Lecturer Name" required>
    <input name=u placeholder="Username" required>
    <input name=p type=password placeholder="Password" required>
    <button>Register</button></form>
    <p>{msg}</p></div>
    """.format(style=STYLE,msg=msg)

# ---------------- STUDENT ----------------
@app.route("/student", methods=["GET","POST"])
def student():
    close_expired()
    sid=request.args.get("id")
    con=db();cur=con.cursor()
    cur.execute("SELECT * FROM sessions WHERE is_active=1")
    s=cur.fetchone()
    msg=""
    if request.method=="POST":
        if not s: msg="No active session"
        else:
            cur.execute("SELECT fingerprint FROM users WHERE id=?", (sid,))
            if cur.fetchone()["fingerprint"]!=hash_fp(request.form["fp"]):
                msg="Fingerprint mismatch"
            elif request.form["qr"]!=s["qr_token"]:
                msg="Invalid QR"
            else:
                try:
                    cur.execute("INSERT INTO attendance VALUES(NULL,?,?,?)",
                    (sid,s["id"],datetime.now()))
                    con.commit(); msg="Your attendance for this class has been recorded successfully"
                except:
                    msg="  Error: Attendance already marked"
    con.close()
    return """
    {style}<div class=card>
    <h2>Student Attendance Page</h2>
    {session_info}
    <video id=video width=100%></video>
    <canvas id=canvas hidden></canvas>
    <form method=post>
    <input id=qr name=qr placeholder="QR result" required>
    <input name=fp placeholder="Fingerprint Code eg:FP1001" required>
    <button>Submit</button></form>
    <p>{msg}</p></div>

<script src="https://unpkg.com/jsqr"></script>
<script>
navigator.mediaDevices.getUserMedia({{video:{{facingMode:"environment"}}}})
.then(stream=>{{
video.srcObject=stream;video.play();
setInterval(()=>{{
canvas.width=video.videoWidth;
canvas.height=video.videoHeight;
canvas.getContext("2d").drawImage(video,0,0);
let img=canvas.getContext("2d").getImageData(0,0,canvas.width,canvas.height);
let code=jsQR(img.data,canvas.width,canvas.height);
if(code) qr.value=code.data;
}},1000);
}});
</script>
    """.format(style=STYLE, msg=msg, session_info=("Ends at "+s["end_time"]) if s else "No active session")

# ---------------- LECTURER DASHBOARD ----------------
@app.route("/lecturer")
def lecturer():
    close_expired()
    lid=request.args.get("id")
    con=db();cur=con.cursor()
    cur.execute("SELECT * FROM sessions WHERE is_active=1 AND lecturer_id=?", (lid,))
    s=cur.fetchone()
    qr_img = "<img src='data:image/png;base64,{}'>".format(qr_image(s['qr_token'])) if s else ""
    con.close()
    return """
    {style}<div class=card>
    <h2>Lecturer Page</h2>
    {qr_img}
    {session_info}
    <a href=/start?id={lid}><button>Start New Session</button></a>
    <a href=/end><button class=end>End Session</button></a>
    <a href=/analysis><button> Attendance Analytics</button></a>
    <a href=/report?id={lid}><button>Student attendance Report</button></a>
    </div>
    """.format(style=STYLE, qr_img=qr_img, session_info=("Ends at "+s["end_time"]) if s else "No active session", lid=lid)

# ---------------- START SESSION ----------------
@app.route("/start")
def start():
    lid=request.args.get("id")
    con=db();cur=con.cursor()
    cur.execute("UPDATE sessions SET is_active=0")
    qr=str(uuid.uuid4())[:8]
    st=datetime.now();et=st+timedelta(minutes=10)
    cur.execute("INSERT INTO sessions VALUES(NULL,?,?,?,?,?)",(lid,st,et,1,qr))
    con.commit();con.close()
    return redirect("/lecturer?id={}".format(lid))

# ---------------- END SESSION ----------------
@app.route("/end")
def end():
    con=db();con.execute("UPDATE sessions SET is_active=0")
    con.commit();con.close()
    return redirect("/")

# ---------------- ANALYTICS ----------------
@app.route("/analysis")
def analysis():
    con=db();cur=con.cursor()
    cur.execute("""
    SELECT sessions.id, COUNT(attendance.id) c
    FROM sessions LEFT JOIN attendance
    ON sessions.id=attendance.session_id
    GROUP BY sessions.id
    """)
    rows=cur.fetchall();con.close()
    li="".join(["<li>Session {}: {} students</li>".format(r['id'],r['c']) for r in rows])
    return "{style}<div class=card><h2>Student attendance Analytics</h2><ul>{li}</ul></div>".format(style=STYLE,li=li)

# ---------------- ATTENDANCE REPORT (Grouped by Session) ----------------
@app.route("/report")
def report():
    lid=request.args.get("id")
    con = db(); cur = con.cursor()
    cur.execute("""
    SELECT a.id as attendance_id, a.time, u.name, u.matric, s.id as session_id
    FROM attendance a
    JOIN users u ON a.student_id=u.id
    JOIN sessions s ON a.session_id=s.id
    ORDER BY s.id DESC, a.time ASC
    """)
    rows = cur.fetchall(); con.close()
    
    grouped = {}
    for r in rows:
        grouped.setdefault(r['session_id'], []).append(r)
    
    html = ""
    for session_id, records in grouped.items():
        html += "<div class=card><h3>Session {}</h3>".format(session_id)
        html += "<table><tr><th>Student Name</th><th>Matric Number</th><th>Date & Time</th></tr>"
        for r in records:
            html += "<tr><td>{}</td><td>{}</td><td>{}</td></tr>".format(r['name'], r['matric'], r['time'])
        html += "</table></div>"
    
    html += "<div class=card><a href=/report_csv?id={lid}><button>Download CSV</button></a>".format(lid=lid)
    html += "<a href=/lecturer?id={lid}><button>Go back to Dashboard</button></a></div>".format(lid=lid)
    
    return STYLE + html

# ---------------- ATTENDANCE CSV EXPORT ----------------
@app.route("/report_csv")
def report_csv():
    con = db(); cur = con.cursor()
    cur.execute("""
    SELECT a.id as attendance_id, a.time, u.name, u.matric, s.id as session_id
    FROM attendance a
    JOIN users u ON a.student_id=u.id
    JOIN sessions s ON a.session_id=s.id
    ORDER BY s.id DESC, a.time ASC
    """)
    rows = cur.fetchall(); con.close()
    
    si = StringIO()
    writer = csv.writer(si)
    writer.writerow(["Session ID","Student Name","Matric Number","Date & Time"])
    for r in rows:
        writer.writerow([r['session_id'], r['name'], r['matric'], r['time']])
    
    output = si.getvalue()
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition":"attachment;filename=attendance_report.csv"}
    )

# ---------------- RUN ----------------
if __name__=="__main__":
    app.run(debug=True)