# app.py
import os
import io
from datetime import datetime
from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, send_from_directory, send_file
)
from pymongo import MongoClient
import certifi
from bson.objectid import ObjectId
import pandas as pd
from dotenv import load_dotenv
from utils import hash_password, check_password, save_file

# PDF generation
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

# ----------------- Config & Setup -----------------
load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret")

MONGO_URI = os.getenv("MONGO_URI")
UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "static/uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ----------------- Helpers -----------------
def teacher_required(f):
    from functools import wraps
    @wraps(f)
    def wrapper(*args, **kwargs):
        u = session.get("user")
        if not u or u.get("role") != "teacher":
            db = get_db()
            flash("Teacher login required", "danger")
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return wrapper

def login_required(f):
    from functools import wraps
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            db = get_db()
            flash("Login required", "warning")
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return wrapper

def get_db():
    """Get a new database connection."""
    client = MongoClient(MONGO_URI, tls=True, tlsCAFile=certifi.where())
    return client.get_database()

# ----------------- Seeds -----------------
def seed_defaults():
    db = get_db()
    # Seed a default teacher if none exists (username: teacher, password: password)
    if db.teachers.count_documents({}) == 0:
        db.teachers.insert_one({
            "username": "teacher",
            "password": hash_password("password"),
            "name": "Default Teacher",
            "branch": "CSE",
            "created_at": datetime.utcnow()
        })

    # Seed branches if empty
    if db.branches.count_documents({}) == 0:
        seed = [
            {"code": "CSE", "name": "CSE", "password": hash_password("csepass")},
            {"code": "AIDS", "name": "CS-AIDS", "password": hash_password("aids123")},
            {"code": "AIML", "name": "AIML", "password": hash_password("aimlpass")},
            {"code": "CIVIL", "name": "CIVIL", "password": hash_password("civil123")}
        ]
        db.branches.insert_many(seed)

# ----------------- Routes -----------------
@app.route("/")
def index():
    """Home page with a single Login button (modal on frontend)."""
    return render_template("landing.html",current_year=datetime.now().year)


@app.route("/login", methods=["GET", "POST"])
def login():
    """
    Handles both teacher and student login.
    Expects form fields: role, username, password
    """
    if request.method == "POST":
        role = request.form.get("role")
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        db = get_db()
        if role == "teacher":
            teacher = db.teachers.find_one({"username": username})
            if teacher and check_password(password, teacher["password"]):
                session["user"] = {
                    "username": username,
                    "role": "teacher",
                    "branch": teacher.get("branch")
                }
                flash("Teacher logged in", "success")
                return redirect(url_for("teacher_dashboard"))
            else:
                flash("Invalid teacher credentials", "danger")
                return redirect(url_for("index"))

        elif role == "student":
            student = db.students.find_one({"username": username})
            if student and check_password(password, student["password"]):
                session["user"] = {
                    "username": username,
                    "role": "student",
                    "usn": student.get("usn"),
                    "branch": student.get("branch"),
                    "semester": student.get("semester")
                }
                flash("Student logged in", "success")
                return redirect(url_for("student_dashboard"))
            else:
                flash("Invalid student credentials", "danger")
                return redirect(url_for("index"))

        else:
            flash("Please select a valid role", "warning")
            return redirect(url_for("index"))

    # If GET, show login page (useful if someone opens /login directly)
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully", "info")
    return redirect(url_for("index"))


# ----------------- Teacher Pages -----------------
@app.route("/teacher")
@teacher_required
def teacher_dashboard():
    u = session.get("user")
    db = get_db()
    teacher = db.teachers.find_one({"username": u["username"]}) if u else None
    try:
        branches = list(db.branches.find())
    except Exception:
        branches = []
    return render_template("teacher_dashboard.html", teacher=teacher, branches=branches)


@app.route("/teacher/branch/<code>", methods=["GET", "POST"])
@teacher_required
def branch_view(code):
    """
    Branch password check page.
    On POST verifies branch password and sets session['branch'].
    """
    db = get_db()
    branch = db.branches.find_one({"code": code})
    if not branch:
        flash("Branch not found", "danger")
        return redirect(url_for("teacher_dashboard"))

    if request.method == "POST":
        bpw = request.form.get("branch_password", "").strip()
        if not check_password(bpw, branch["password"]):
            flash("Incorrect branch password", "danger")
            return redirect(url_for("teacher_dashboard"))
        session["branch"] = code
        flash(f"Entered branch {code}", "success")
        return redirect(url_for("branch_dashboard", code=code))

    return render_template("branch_password.html", branch=branch)


@app.route("/teacher/branch/<code>/dashboard")
@teacher_required
def branch_dashboard(code):
    """
    Branch control panel where teacher uploads students, adds manually, deletes students,
    and picks a semester to enter marks.
    """
    if session.get("branch") != code:
        flash("Enter branch password first", "danger")
        return redirect(url_for("branch_view", code=code))

    db = get_db()
    branch = db.branches.find_one({"code": code})
    semesters = list(range(1, 8))
    return render_template("branch_dashboard.html", branch=branch, semesters=semesters)


@app.route("/teacher/branch/<code>/upload_students", methods=["GET", "POST"])
@teacher_required
def upload_students(code):
    """Upload students CSV for a specific branch — auto-assign branch from URL and sort by serial number."""
    if session.get("branch") != code:
        flash("Enter branch password first", "danger")
        return redirect(url_for("branch_view", code=code))

    if request.method == "POST":
        file = request.files.get("students_file")
        if not file:
            flash("Attach CSV or Excel file", "danger")
            return redirect(request.url)

        try:
            filename = file.filename.lower()
            if filename.endswith(".csv"):
                df = pd.read_csv(file)
            else:
                df = pd.read_excel(file)
        except Exception as e:
            flash(f"File read error: {e}", "danger")
            return redirect(request.url)

        import re
        # Define valid USN patterns per branch
        branch_patterns = {
            "CSE": re.compile(r"^(21|22|23)SECD\d{1,3}$", re.IGNORECASE),
            "AIML": re.compile(r"^(21|22|23)SEAI\d{1,3}$", re.IGNORECASE),
            "DS": re.compile(r"^(21|22|23)SEAD\d{1,3}$", re.IGNORECASE),
            "CIVIL": re.compile(r"^(21|22|23)SECV\d{1,3}$", re.IGNORECASE),
        }

        pattern = branch_patterns.get(code.upper())
        if not pattern:
            flash(f"No USN pattern defined for branch {code.upper()}", "danger")
            return redirect(request.url)

        valid_rows = []
        skipped = 0

        # Validate rows and extract serial numbers
        for _, row in df.iterrows():
            name = str(row.get("name", "")).strip()
            usn = str(row.get("usn", "")).strip().upper()

            if not name or not usn:
                skipped += 1
                continue

            if not pattern.match(usn):
                skipped += 1
                continue

            try:
                serial_num = int(re.findall(r"\d{1,3}$", usn)[0])
            except Exception:
                skipped += 1
                continue

            try:
                year = int(row.get("year", 1))
            except Exception:
                year = 1

            try:
                semester = int(row.get("semester", 1))
            except Exception:
                semester = 1

            valid_rows.append({
                "name": name,
                "usn": usn,
                "serial": serial_num,
                "year": year,
                "semester": semester
            })

        # Sort students by serial number
        valid_rows = sorted(valid_rows, key=lambda x: x["serial"])

        db = get_db()
        added = 0

        for student in valid_rows:
            username = student["name"].lower().replace(" ", ".")
            password_hash = hash_password(student["usn"])

            doc = {
                "name": student["name"],
                "usn": student["usn"],
                "username": username,
                "password": password_hash,
                "branch": code.upper(),
                "year": student["year"],
                "semester": student["semester"],
                "created_at": datetime.utcnow()
            }

            db.students.update_one({"usn": student["usn"]}, {"$set": doc}, upsert=True)
            added += 1

        flash(
            f"✅ Uploaded {added} students to {code.upper()} branch (sorted by USN). Skipped {skipped} invalid or missing rows.",
            "success"
        )
        return redirect(url_for("branch_dashboard", code=code))

    return render_template("upload_students.html", branch_code=code)


@app.route("/teacher/branch/<code>/add_student", methods=["GET", "POST"])
@teacher_required
def add_student_branch(code):
    if session.get("branch") != code:
        flash("Enter branch password first", "danger")
        return redirect(url_for("branch_view", code=code))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        usn = request.form.get("usn", "").strip()
        try:
            year = int(request.form.get("year", 1))
        except Exception:
            year = 1
        try:
            semester = int(request.form.get("semester", 1))
        except Exception:
            semester = 1

        if not usn:
            flash("USN required", "danger")
            return redirect(request.url)

        db = get_db()
        username = name.lower().replace(" ", ".") if name else usn
        pwd = hash_password(usn)
        doc = {
            "name": name,
            "usn": usn,
            "username": username,
            "password": pwd,
            "branch": code,
            "year": year,
            "semester": semester,
            "created_at": datetime.utcnow()
        }
        db.students.update_one({"usn": usn}, {"$set": doc}, upsert=True)
        flash("Student added/updated", "success")
        return redirect(url_for("branch_dashboard", code=code))

    return render_template("add_student.html", branch_code=code)


@app.route("/teacher/branch/<code>/delete_student/<usn>", methods=["POST"])
@teacher_required
def delete_student_branch(code, usn):
    if session.get("branch") != code:
        flash("Enter branch password first", "danger")
        return redirect(url_for("branch_view", code=code))

    db = get_db()
    db.students.delete_one({"usn": usn, "branch": code})
    for s in range(1, 8):
        db[f"marks_sem{s}"].delete_many({"usn": usn})
    flash(f"Deleted {usn}", "info")
    return redirect(url_for("branch_dashboard", code=code))


@app.route("/teacher/branch/<code>/semester/<int:sem>")
@teacher_required
def semester_marks(code, sem):
    if session.get("branch") != code:
        flash("Enter branch password first", "danger")
        return redirect(url_for("branch_view", code=code))

    db = get_db()
    students = list(db.students.find({"branch": code, "semester": sem}).sort("usn", 1))
    marks_col = db[f"marks_sem{sem}"]
    subjects = ["Subject1", "Subject2", "Subject3"]

    rows = []
    for st in students:
        mdoc = marks_col.find_one({"usn": st["usn"]})
        marks = mdoc["marks"] if mdoc and "marks" in mdoc else {
            s: {"IA1": "", "IA2": "", "IA3": "", "attendance": ""} for s in subjects
        }
        rows.append({"student": st, "marks": marks})

    return render_template("semester_marks.html", branch=code, semester=sem, rows=rows, subjects=subjects)


@app.route("/teacher/branch/<code>/semester/<int:sem>/save", methods=["POST"])
@teacher_required
def save_all_marks(code, sem):
    if session.get("branch") != code:
        flash("Enter branch password first", "danger")
        return redirect(url_for("branch_view", code=code))

    db = get_db()
    marks_col = db[f"marks_sem{sem}"]
    subjects = ["Subject1", "Subject2", "Subject3"]
    usn_list = request.form.getlist("usn_list")
    processed = 0

    for usn in usn_list:
        marks_obj = {}
        for s in subjects:
            IA1 = request.form.get(f"{usn}__{s}__IA1", "")
            IA2 = request.form.get(f"{usn}__{s}__IA2", "")
            IA3 = request.form.get(f"{usn}__{s}__IA3", "")
            att = request.form.get(f"{usn}__{s}__ATT", "")
            marks_obj[s] = {"IA1": IA1, "IA2": IA2, "IA3": IA3, "attendance": att}

        student = db.students.find_one({"usn": usn})
        doc = {
            "usn": usn,
            "name": student.get("name"),
            "branch": code,
            "semester": sem,
            "marks": marks_obj,
            "updated_at": datetime.utcnow()
        }
        marks_col.update_one({"usn": usn}, {"$set": doc}, upsert=True)
        processed += 1

    flash(f"Saved marks for {processed} students", "success")
    return redirect(url_for("semester_marks", code=code, sem=sem))


@app.route("/teacher/branch/<code>/semester/<int:sem>/reset/<usn>", methods=["POST"])
@teacher_required
def reset_student_marks(code, sem, usn):
    if session.get("branch") != code:
        flash("Enter branch password first", "danger")
        return redirect(url_for("branch_view", code=code))

    db = get_db()
    db[f"marks_sem{sem}"].delete_many({"usn": usn})
    flash(f"Reset marks for {usn}", "info")
    return redirect(url_for("semester_marks", code=code, sem=sem))


# ----------------- Student Pages -----------------
@app.route("/student_dashboard")
@login_required
def student_dashboard():
    u = session.get("user")
    if not u or u.get("role") != "student":
        flash("Student login required", "danger")
        return redirect(url_for("login"))

    db = get_db()
    username = u.get("username")
    student = db.students.find_one({"username": username})
    if not student:
        flash("Student record not found", "danger")
        return redirect(url_for("login"))

    sem = int(student.get("semester", 1))
    marks_col = db.get_collection(f"marks_sem{sem}")
    mdoc = marks_col.find_one({"usn": student.get("usn")})
    subjects = ["Subject1", "Subject2", "Subject3"]
    marks = (
        mdoc.get("marks", {})
        if mdoc
        else {s: {"IA1": "", "IA2": "", "IA3": "", "attendance": ""} for s in subjects}
    )

    return render_template(
        "student_dashboard.html",
        name=student.get("name", ""),
        usn=student.get("usn", ""),
        branch=student.get("branch", ""),
        semester=sem,
        marks=marks,
        subjects=subjects,
        notes=list(db.notes.find({"branch": student.get("branch"), "semester": sem}).sort("created_at", -1))
    )


@app.route("/download_marksheet/<int:semester>")
@login_required
def download_marksheet(semester):
    """
    Generates a professional, reusable PDF marksheet with branding, watermark,
    and formatted IA + Attendance details for a student.
    """

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, Image
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from datetime import datetime

    u = session.get("user")
    if not u or u.get("role") != "student":
        flash("Student login required", "danger")
        return redirect(url_for("index"))

    db = get_db()
    student = db.students.find_one({"username": u["username"]})
    if not student:
        return "Student not found."

    usn = student.get("usn")
    name = student.get("name", "")
    branch = student.get("branch", "")
    semester = int(student.get("semester", semester))

    marks_col = db.get_collection(f"marks_sem{semester}")
    mdoc = marks_col.find_one({"usn": usn})
    if not mdoc:
        return "No marks found for this semester."

    marks = mdoc.get("marks", {})
    subjects = list(marks.keys())

    # ---- Calculate summary ----
    total_ia_sum = sum(sum(int(marks[sub].get(k, 0)) for k in ["IA1", "IA2", "IA3"]) for sub in subjects)
    total_ia_count = len(subjects) * 3 if subjects else 1
    avg_ia = round(total_ia_sum / total_ia_count, 2)
    avg_att = round(sum(int(marks[sub].get("attendance", 0)) for sub in subjects) / len(subjects), 1)

    # ---- PDF Setup ----
    buffer = io.BytesIO()
    pdf = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=60,
        bottomMargin=50,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "title",
        fontName="Helvetica-Bold",
        fontSize=20,
        textColor=colors.HexColor("#FF4B2B"),
        alignment=1,
        spaceAfter=10,
    )
    normal_style = ParagraphStyle(
        "normal",
        fontName="Helvetica",
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#333333"),
    )

    elements = []

    # ---- Header ----
    logo_path = os.path.join("static", "logo.png")
    if os.path.exists(logo_path):
        elements.append(Image(logo_path, width=70, height=70))
    elements.append(Paragraph("<b>COLLEGE OF ENGINEERING</b>", title_style))
    elements.append(Paragraph("Internal Assessment Marksheet", styles["Normal"]))
    elements.append(Spacer(1, 12))

    # ---- Student Info ----
    info_html = f"""
    <b>Name:</b> {name}<br/>
    <b>USN:</b> {usn}<br/>
    <b>Branch:</b> {branch}<br/>
    <b>Semester:</b> {semester}
    """
    elements.append(Paragraph(info_html, normal_style))
    elements.append(Spacer(1, 18))

    # ---- Watermark ----
    def draw_watermark(canvas_obj, doc):
        canvas_obj.saveState()
        canvas_obj.setFont("Helvetica-Bold", 42)
        canvas_obj.setFillGray(0.9, 0.1)
        canvas_obj.rotate(45)
        canvas_obj.drawString(200, 150, "INTERNAL ASSESSMENT REPORT")
        canvas_obj.restoreState()

    # ---- Table ----
    data = [["Subject", "IA1", "IA2", "IA3", "Attendance (%)", "Total (90)", "Status"]]
    for sub, v in marks.items():
        ia1 = int(v.get("IA1", 0))
        ia2 = int(v.get("IA2", 0))
        ia3 = int(v.get("IA3", 0))
        att = int(v.get("attendance", 0))
        total = ia1 + ia2 + ia3
        status = "Eligible" if att >= 75 else "Shortage"
        data.append([sub, ia1, ia2, ia3, att, total, status])

    table = Table(
        data,
        colWidths=[2.3 * inch, 0.6 * inch, 0.6 * inch, 0.6 * inch, 1.1 * inch, 0.8 * inch, 1.1 * inch],
        hAlign="CENTER",
    )

    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#FF6F3C")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.Color(1, 0.97, 0.93)]),
            ]
        )
    )
    elements.append(table)
    elements.append(Spacer(1, 25))

    # ---- Summary ----
    summary_html = f"""
    <para align='center'>
    <font size=12 color='#FF4B2B'>
    <b>Average IA Score:</b> {avg_ia} &nbsp;&nbsp;|&nbsp;&nbsp;
    <b>Average Attendance:</b> {avg_att}%<br/>
    <b>Date Generated:</b> {datetime.now().strftime('%d %B %Y')}
    </font>
    </para>
    """
    elements.append(Paragraph(summary_html, styles["Normal"]))
    elements.append(Spacer(1, 15))

    # ---- Footer ----
    footer_html = """
    <para align='center'>
    <font size=9 color='#999999'>
    Generated by College Portal | This is a system-generated report.
    </font>
    </para>
    """
    elements.append(Paragraph(footer_html, styles["Normal"]))

    # ---- Build ----
    pdf.build(elements, onFirstPage=draw_watermark, onLaterPages=draw_watermark)

    buffer.seek(0)
    filename = f"{name.replace(' ', '_')}_Sem{semester}_Marksheet.pdf"
    return send_file(buffer, as_attachment=True, download_name=filename, mimetype="application/pdf")


# Serve uploaded files (optional)
@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


# ----------------- Notes -----------------
@app.route("/teacher/branch/<code>/upload_notes", methods=["GET", "POST"])
@teacher_required
def upload_notes(code):
    """
    Upload notes per semester, subject, and module — uniquely designed system.
    """
    if session.get("branch") != code:
        flash("Enter branch password first", "danger")
        return redirect(url_for("branch_view", code=code))

    # Example subjects (replace later with subject_config if needed)
    subjects = {
        1: ["Physics", "Mathematics", "Civil", "Electronics"],
        2: ["Chemistry", "Programming", "Electricals", "Mechanical"],
        3: ["Data Structures", "Software Engineering", "Math III"],
        4: ["OS", "DBMS", "Microprocessors"],
        5: ["AI", "ML", "Web Tech"],
        6: ["Networks", "Cloud Computing"],
        7: ["Big Data", "Cyber Security"],
        8: ["Project", "Internship"]
    }

    # 5 module options per subject
    modules = [f"Module {i}" for i in range(1, 6)]

    if request.method == "POST":
        try:
            semester = int(request.form.get("semester"))
        except (ValueError, TypeError):
            flash("⚠️ Semester must be a number", "danger")
            return redirect(request.url)

        subject = request.form.get("subject", "").strip()
        module = request.form.get("module", "").strip()
        file = request.files.get("file")

        if not all([semester, subject, module, file]):
            flash("⚠️ All fields are required", "danger")
            return redirect(request.url)

        # Save file
        db = get_db()
        filepath = save_file(file, UPLOAD_FOLDER)
        if not filepath:
            flash("❌ Error saving file. Try again.", "danger")
            return redirect(request.url)

        # Save details in DB
        doc = {
            "branch": code.upper(),
            "semester": semester,
            "subject": subject,
            "module": module,
            "filename": os.path.basename(filepath),
            "filepath": filepath,
            "created_at": datetime.utcnow(),
            "uploader": session.get("user", {}).get("username")
        }

        db.notes.insert_one(doc)
        flash(f"✅ Notes uploaded successfully for {subject} ({module})", "success")
        return redirect(request.url)

    return render_template(
        "upload_notes.html",
        branch_code=code,
        subjects=subjects,
        modules=modules
    )

@app.route("/student/marks")
@login_required
def student_view_marks():
    u = session.get("user")
    if u.get("role") != "student":
        flash("Student login required", "danger")
        return redirect(url_for("index"))

    db = get_db()
    student = db.students.find_one({"username": u["username"]})
    sem = int(student.get("semester", 1))
    marks_col = db.get_collection(f"marks_sem{sem}")
    mdoc = marks_col.find_one({"usn": student["usn"]})
    marks = mdoc["marks"] if mdoc else {}
    return render_template("student_view_marks.html", marks=marks, semester=sem)

@app.route("/student/view_marks")
@login_required
def student_auto_view_marks():
    u = session.get("user")
    if not u or u.get("role") != "student":
        flash("Student login required", "danger")
        return redirect(url_for("login"))

    db = get_db()
    student = db.students.find_one({"username": u["username"]})
    semester = int(student.get("semester", 1))
    return redirect(url_for("view_marks", semester=semester))
@app.route("/student/view_marks/<int:semester>")
@login_required
def view_marks(semester):
    """
    Fetch and display marks for a logged-in student (MongoDB Atlas version),
    including correct numeric calculations for IA averages and attendance.
    """

    # ---------------- Authentication ----------------
    u = session.get("user")
    if not u or u.get("role") != "student":
        flash("Student login required", "danger")
        return redirect(url_for("login"))

    db = get_db()
    username = u.get("username")

    # ---------------- Fetch Student ----------------
    student = db.students.find_one({"username": username})
    if not student:
        flash("Student record not found.", "danger")
        return redirect(url_for("student_dashboard"))

    name = student.get("name", "N/A")
    usn = student.get("usn", "N/A")
    branch = student.get("branch", "N/A")
    semester = int(student.get("semester", semester))

    # ---------------- Fetch Marks ----------------
    marks_col = db.get_collection(f"marks_sem{semester}")
    mdoc = marks_col.find_one({"usn": usn})
    subjects = ["Subject1", "Subject2", "Subject3"]

    if mdoc and "marks" in mdoc:
        marks = mdoc["marks"]
    else:
        marks = {sub: {"IA1": "", "IA2": "", "IA3": "", "attendance": ""} for sub in subjects}

    # ---------------- Convert and Calculate ----------------
    total_ia_sum = 0
    total_ia_count = 0
    total_attendance = 0
    total_subjects = len(marks)
    top_subject = None
    top_total = -1

    for sub, m in marks.items():
        for key in ["IA1", "IA2", "IA3", "attendance"]:
            # Safely convert strings to integers
            try:
                marks[sub][key] = int(m.get(key, 0))
            except Exception:
                marks[sub][key] = 0

        # Compute totals
        ia_sum = marks[sub]["IA1"] + marks[sub]["IA2"] + marks[sub]["IA3"]
        total_ia_sum += ia_sum
        total_ia_count += 3
        total_attendance += marks[sub]["attendance"]

        # Find top performing subject
        if ia_sum > top_total:
            top_total = ia_sum
            top_subject = sub

    # Calculate averages
    avg_ia = round(total_ia_sum / total_ia_count, 1) if total_ia_count > 0 else 0
    avg_attendance = round(total_attendance / total_subjects, 1) if total_subjects > 0 else 0

    # ---------------- Render Template ----------------
    return render_template(
        "student_view_marks.html",
        name=name,
        usn=usn,
        branch=branch,
        semester=semester,
        marks=marks,
        subjects=subjects,
        avg_ia=avg_ia,
        avg_attendance=avg_attendance,
        top_subject=top_subject
    )

@app.route("/student/notes")
@login_required
def student_view_notes():
    u = session.get("user")
    if u.get("role") != "student":
        flash("Student login required", "danger")
        return redirect(url_for("index"))

    db = get_db()
    student = db.students.find_one({"username": u["username"]})
    if not student:
        flash("Student not found", "danger")
        return redirect(url_for("login"))

    sem = int(student.get("semester", 1))
    branch = student.get("branch")

    # ✅ Fetch subjects from marks collection
    marks_col = db.get_collection(f"marks_sem{sem}")
    marks_doc = marks_col.find_one({"usn": student["usn"]})
    subjects = list(marks_doc["marks"].keys()) if marks_doc and "marks" in marks_doc else []

    # ✅ Fetch uploaded notes for the branch & semester
    notes_cursor = list(db.notes.find({"branch": branch, "semester": sem}))
    uploaded = {}

    # Normalize note subjects for fuzzy matching
    def normalize(text):
        return text.strip().lower().replace(" ", "")

    for n in notes_cursor:
        subject_name = n["subject"]
        module = n.get("module", "Module 1")
        normalized_sub = normalize(subject_name)
        if normalized_sub not in uploaded:
            uploaded[normalized_sub] = {}
        uploaded[normalized_sub][module] = {
            "id": str(n["_id"]),
            "filename": n.get("filename", "Unknown file")
        }

    # ✅ Build full notes dictionary
    full_notes = {}
    for subject in subjects:
        normalized_sub = normalize(subject)
        full_notes[subject] = []
        for i in range(1, 6):
            module_name = f"Module {i}"
            if normalized_sub in uploaded and module_name in uploaded[normalized_sub]:
                full_notes[subject].append({
                    "module": module_name,
                    "uploaded": True,
                    "id": uploaded[normalized_sub][module_name]["id"],
                    "filename": uploaded[normalized_sub][module_name]["filename"]
                })
            else:
                full_notes[subject].append({
                    "module": module_name,
                    "uploaded": False
                })

    return render_template(
        "student_view_notes.html",
        name=student.get("name"),
        semester=sem,
        notes=full_notes
    )

@app.route("/download_note/<note_id>")
@login_required
def download_note(note_id):
    db = get_db()
    note = db.notes.find_one({"_id": ObjectId(note_id)})
    if not note:
        return "File not found", 404
    return send_from_directory(os.path.dirname(note['filepath']), os.path.basename(note['filepath']), as_attachment=True)

# ----------------- Run -----------------
if __name__ == "__main__":
    # Initialize Mongo client and seed data only when running directly
    with app.app_context():
        try:
            seed_defaults()
        except Exception as e:
            print("⚠️ Warning: could not seed defaults:", e)
    app.run(debug=True)