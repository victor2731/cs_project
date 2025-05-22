import sqlite3
from flask import Flask, render_template, request, redirect, session
from flask_session import Session
from werkzeug.security import generate_password_hash, check_password_hash
from helpers import login_required
import os
from werkzeug.utils import secure_filename

UPLOAD_FOLDER = "static/submissions"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "pdf", "mp3", "mp4"}

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Database connection
def get_db_connection():
    conn = sqlite3.connect("music_school.db")
    conn.row_factory = sqlite3.Row
    return conn
# ---------------------- index ----------------------
@app.route("/")
def index():
    return render_template("index.html")

# ---------------------- Student Registration ----------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == "POST":
        first_name = request.form.get("first_name")
        last_name = request.form.get("last_name")
        email = request.form.get("email")
        password = request.form.get("password")
        teacher_id = request.form.get("teacher_id")
        instrument = request.form.get("instrument")

        hashed_password = generate_password_hash(password)
    
        cursor.execute(
            "INSERT INTO users (first_name, last_name, email, password, teacher_id, instrument, score) VALUES (?, ?, ?, ?, ?, ?, ?)", 
            (first_name, last_name, email, hashed_password, teacher_id, instrument, 0)
        )
        conn.commit()
        conn.close()
        return redirect("/login")  

    teachers = cursor.execute("SELECT id, name, instruments FROM teachers").fetchall()
    conn.close()
    
    return render_template("register.html", teachers=teachers)

# ---------------------- Student Login ----------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        user = cursor.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            return redirect("/dashboard")

        return "Invalid email or password"

    return render_template("login.html")

# ---------------------- Student Dashboard ----------------------
@app.route("/dashboard")
@login_required
def dashboard():
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()
    cursor = conn.cursor()

    user = cursor.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    teacher = cursor.execute("SELECT * FROM teachers WHERE id = ?", (user["teacher_id"],)).fetchone()
   # Fetch tasks along with feedback
    tasks = cursor.execute("SELECT id, description, due_date, feedback FROM tasks WHERE student_id = ?", (session["user_id"],)).fetchall()
    sub = cursor.execute("SELECT id, description, status from tasks WHERE student_id = ?", (session["user_id"],)).fetchall()
    
    conn.close()
    return render_template("dashboard.html", user=user, teacher=teacher, tasks=tasks, sub=sub)

# ---------------------- Teacher Login ----------------------
@app.route("/teacher_login", methods=["GET", "POST"])
@login_required
def teacher_login():
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == "POST":
        email = request.form.get("email")

        teacher = cursor.execute("SELECT * FROM teachers WHERE email = ?", (email,)).fetchone()

        if teacher:
            session["teacher_id"] = teacher["id"]
            return redirect("/teacher_dashboard")

        return "Invalid email"

    return render_template("teacher_login.html")

# ---------------------- Teacher Dashboard ----------------------
@app.route("/teacher_dashboard")
@login_required
def teacher_dashboard():
    if "teacher_id" not in session:
        return redirect("/teacher_login")

    conn = get_db_connection()
    cursor = conn.cursor()

    teacher = cursor.execute("SELECT * FROM teachers WHERE id = ?", (session["teacher_id"],)).fetchone()
    students = cursor.execute("SELECT * FROM users WHERE teacher_id = ?", (session["teacher_id"],)).fetchall()
    student_doubts = cursor.execute("SELECT doubts, first_name, last_name AS student_name FROM users WHERE teacher_id = ?", (session["teacher_id"],)).fetchall()
    
    # Fetch tasks including submissions
    completed_tasks = cursor.execute("""
        SELECT tasks.id, tasks.description, tasks.submissions, tasks.feedback, 
               users.first_name || ' ' || users.last_name AS student_name
        FROM tasks
        JOIN users ON tasks.student_id = users.id
        WHERE tasks.status = 'completed' AND tasks.teacher_id = ?
    """, (session["teacher_id"],)).fetchall()

    conn.close()
    return render_template("teacher_dashboard.html", teacher=teacher, students=students, completed_tasks=completed_tasks, student_doubts=student_doubts)

# ---------------------- Assign Tasks to Students ----------------------
@app.route("/assign_task", methods=["POST"])
@login_required
def assign_task():
    if "teacher_id" not in session:
        return redirect("/teacher_login")

    conn = get_db_connection()
    cursor = conn.cursor()

    student_id = request.form.get("student_id")
    description = request.form.get("description")
    due_date = request.form.get("due_date")
    feedback_text = request.form.get("feedback_text")
    

    cursor.execute("INSERT INTO tasks (teacher_id, student_id, description, due_date, feedback) VALUES (?, ?, ?, ?, ?)", (session["teacher_id"], student_id, description, due_date, feedback_text))
    conn.commit()
    conn.close()

    return redirect("/teacher_dashboard")

# ---------------------- Logout ----------------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# ---------------------- Learning Routes ----------------------
@app.route("/learning")
@login_required
def learning():
    return render_template("learning.html")

@app.route("/quiz")
@login_required
def quiz():
    return render_template("quiz.html")
@app.route("/submit_quiz", methods=["POST"])
@login_required
def submit_quiz():
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()
    cursor = conn.cursor()

    # Correct answers & scoring
    correct_answers = {
        "q1": "tempo",        # Speed of a song
        "q2": "6",            # Guitar strings
        "q3": "Keep tempo",   # Metronome use
        "q4": "Strings",      # Violin belongs to Strings family
        "q5": "Raises pitch", # Sharp symbol effect
        "q6": "Staff",        # Five horizontal lines in music notation
        "q7": "Hold a note longer", # Fermata meaning
    }

    score = 0
    for question, answer in correct_answers.items():
        if request.form.get(question) == answer:
            score += 5  # Each correct answer adds 5 points

    # Update the user's score in the database
    cursor.execute("UPDATE users SET score = score + ? WHERE id = ?", (score, session["user_id"]))

    conn.commit()
    conn.close()

    return redirect("/dashboard")

@app.route("/practice")
@login_required
def practice():
    return render_template("practice.html")

@app.route("/lessons")
@login_required
def lessons():
    return render_template("lessons.html")
# ---------------------- Student doubts ----------------------
@app.route("/student_doubts", methods=["POST"])
@login_required
def student_doubts():
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()
    cursor = conn.cursor()

    doubt_text = request.form.get("doubt_text")
    student_id = session["user_id"]

    # Update the student's doubts in users table
    cursor.execute("UPDATE users SET doubts = ? WHERE id = ?", (doubt_text, student_id))

    conn.commit()
    conn.close()

    return redirect("/dashboard")
# ---------------------- Student Submits Task ----------------------
@app.route("/submit_task", methods=["POST"])
@login_required
def submit_task():
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()
    cursor = conn.cursor()

    task_id = request.form.get("task_id")
    file = request.files["submission"]

    if file and file.filename.split(".")[-1] in {"png", "jpg", "jpeg", "pdf", "mp3", "mp4"}:
        filename = secure_filename(file.filename)
        filepath = os.path.join("static/submissions", filename)
        file.save(filepath)
        
        print("file: ", filepath)

        # Store the relative file path in the database **correctly**
        cursor.execute("UPDATE tasks SET submissions = ?, status = 'completed' WHERE id = ?", (filepath, task_id))

        conn.commit()
        conn.close()

    return redirect("/dashboard")

    # ---------------------- validate submissions ----------------------
@app.route("/validate_submission", methods=["POST"])
@login_required
def validate_submission():
    if "teacher_id" not in session:
        return redirect("/teacher_login")

    conn = get_db_connection()
    cursor = conn.cursor()

    task_id = request.form.get("task_id")

    # Update task validation status
    cursor.execute("UPDATE tasks SET status = 'validated' WHERE id = ?", (task_id,))
    
    # Increase student progress score
    student_id = cursor.execute("SELECT student_id FROM tasks WHERE id = ?", (task_id,)).fetchone()["student_id"]
    cursor.execute("UPDATE users SET score = score + 10 WHERE id = ?", (student_id,)).fetchone()

    conn.commit()
    conn.close()

    return redirect("/teacher_dashboard")

# ---------------------- MAIN ----------------------
if __name__ == "__main__":
    app.run(debug=False)
