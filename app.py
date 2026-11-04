
from flask import Flask, render_template, request, redirect, url_for, Response
import mysql.connector
import os
import csv
import io

app = Flask(__name__)


def get_db_connection():
    return mysql.connector.connect(
        host=os.environ["DB_HOST"],
        port=int(os.environ.get("DB_PORT", 4000)),
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        database=os.environ["DB_NAME"],
        ssl_verify_cert=True,
        ssl_verify_identity=True
    
    )


@app.route("/")
def dashboard():
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    try:
        cursor.execute("SELECT COUNT(*) AS total FROM students")
        total_students = cursor.fetchone()["total"]

        cursor.execute("SELECT COUNT(*) AS total FROM mentors")
        total_mentors = cursor.fetchone()["total"]

        cursor.execute("SELECT COUNT(*) AS total FROM mentorhub_assignments")
        total_assignments = cursor.fetchone()["total"]

        cursor.execute("SELECT COUNT(*) AS total FROM mentorhub_meetings")
        total_meetings = cursor.fetchone()["total"]

        stats = {
            "students": total_students,
            "mentors": total_mentors,
            "assignments": total_assignments,
            "meetings": total_meetings
        }

        cursor.execute("""
            SELECT s.student_id,
                   s.student_name AS name,
                   s.department,
                   s.study_year AS year,
                   s.mentor_id,
                   COALESCE(m.mentor_name, 'Not Assigned') AS mentor,
                   CASE WHEN s.mentor_id IS NULL
                        THEN 'Pending' ELSE 'Active' END AS status
            FROM students s
            LEFT JOIN mentors m ON s.mentor_id = m.mentor_id
            ORDER BY s.student_id DESC
        """)
        students = cursor.fetchall()

        cursor.execute("""
            SELECT mentor_id, mentor_name, department
            FROM mentors
            ORDER BY mentor_name
        """)
        mentors = cursor.fetchall()

        cursor.execute("""
            SELECT department, COUNT(*) AS total
            FROM students
            GROUP BY department
            ORDER BY department
        """)
        department_data = cursor.fetchall()

        cursor.execute("""
            SELECT a.assignment_id, a.title, a.description,
                   a.due_date, a.status, a.student_id,
                   COALESCE(s.student_name, 'All Students') AS student_name
            FROM mentorhub_assignments a
            LEFT JOIN students s ON a.student_id = s.student_id
            ORDER BY a.assignment_id DESC
        """)
        assignments = cursor.fetchall()

        cursor.execute("""
            SELECT mt.meeting_id, mt.meeting_date, mt.meeting_time,
                   mt.topic, mt.status, mt.student_id, mt.mentor_id,
                   COALESCE(s.student_name, 'Not selected') AS student_name,
                   COALESCE(m.mentor_name, 'Not assigned') AS mentor_name
            FROM mentorhub_meetings mt
            LEFT JOIN students s ON mt.student_id = s.student_id
            LEFT JOIN mentors m ON mt.mentor_id = m.mentor_id
            ORDER BY mt.meeting_date DESC, mt.meeting_time DESC
        """)
        meetings = cursor.fetchall()

        return render_template(
            "dashboard.html",
            stats=stats,
            students=students,
            mentors=mentors,
            department_data=department_data,
            assignments=assignments,
            meetings=meetings
        )

    finally:
        cursor.close()
        db.close()


# ADD STUDENT
@app.route("/add-student", methods=["POST"])
def add_student():
    name = request.form.get("student_name", "").strip()
    department = request.form.get("department", "").strip()
    year = request.form.get("study_year", "")
    mentor = request.form.get("mentor_id", "")

    if not name or not department or year not in ("1", "2", "3", "4"):
        return "Enter a valid student name, department and study year.", 400

    mentor_id = int(mentor) if mentor.isdigit() else None
    db = get_db_connection()
    cursor = db.cursor()

    try:
        cursor.execute("""
            INSERT INTO students
                (student_name, department, study_year, mentor_id)
            VALUES (%s, %s, %s, %s)
        """, (name, department, int(year), mentor_id))
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        cursor.close()
        db.close()

    return redirect(url_for("dashboard") + "#students")


# DELETE STUDENT
@app.route("/delete-student/<int:student_id>", methods=["POST"])
def delete_student(student_id):
    db = get_db_connection()
    cursor = db.cursor()

    try:
        cursor.execute(
            "DELETE FROM students WHERE student_id = %s",
            (student_id,)
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        cursor.close()
        db.close()

    return redirect(url_for("dashboard") + "#students")


# ADD MENTOR
@app.route("/add-mentor", methods=["POST"])
def add_mentor():
    name = request.form.get("mentor_name", "").strip()
    department = request.form.get("mentor_department", "").strip()

    if not name or not department:
        return "Enter the mentor name and department.", 400

    db = get_db_connection()
    cursor = db.cursor()

    try:
        cursor.execute("""
            INSERT INTO mentors (mentor_name, department)
            VALUES (%s, %s)
        """, (name, department))
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        cursor.close()
        db.close()

    return redirect(url_for("dashboard") + "#mentors")


# DELETE MENTOR
@app.route("/delete-mentor/<int:mentor_id>", methods=["POST"])
def delete_mentor(mentor_id):
    db = get_db_connection()
    cursor = db.cursor()

    try:
        cursor.execute(
            "UPDATE students SET mentor_id = NULL WHERE mentor_id = %s",
            (mentor_id,)
        )
        cursor.execute(
            "DELETE FROM mentors WHERE mentor_id = %s",
            (mentor_id,)
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        cursor.close()
        db.close()

    return redirect(url_for("dashboard") + "#mentors")


# ADD ASSIGNMENT
@app.route("/add-assignment", methods=["POST"])
def add_assignment():
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    student = request.form.get("student_id", "")
    due_date = request.form.get("due_date", "") or None

    if not title:
        return "Please enter an assignment title.", 400

    student_id = int(student) if student.isdigit() else None

    db = get_db_connection()
    cursor = db.cursor()

    try:
        cursor.execute("""
            INSERT INTO mentorhub_assignments
                (title, description, student_id, due_date, status)
            VALUES (%s, %s, %s, %s, 'Pending')
        """, (title, description, student_id, due_date))
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        cursor.close()
        db.close()

    return redirect(url_for("dashboard") + "#assignments")


# DELETE ASSIGNMENT
@app.route("/delete-assignment/<int:assignment_id>", methods=["POST"])
def delete_assignment(assignment_id):
    db = get_db_connection()
    cursor = db.cursor()

    try:
        cursor.execute(
            "DELETE FROM mentorhub_assignments WHERE assignment_id = %s",
            (assignment_id,)
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        cursor.close()
        db.close()

    return redirect(url_for("dashboard") + "#assignments")


# ADD MEETING
@app.route("/add-meeting", methods=["POST"])
def add_meeting():
    student = request.form.get("student_id", "")
    mentor = request.form.get("mentor_id", "")
    meeting_date = request.form.get("meeting_date", "")
    meeting_time = request.form.get("meeting_time", "") or None
    topic = request.form.get("topic", "").strip()

    if not meeting_date or not topic:
        return "Please enter the meeting date and topic.", 400

    student_id = int(student) if student.isdigit() else None
    mentor_id = int(mentor) if mentor.isdigit() else None

    db = get_db_connection()
    cursor = db.cursor()

    try:
        cursor.execute("""
            INSERT INTO mentorhub_meetings
                (student_id, mentor_id, meeting_date, meeting_time,
                 topic, status)
            VALUES (%s, %s, %s, %s, %s, 'Scheduled')
        """, (student_id, mentor_id, meeting_date, meeting_time, topic))
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        cursor.close()
        db.close()

    return redirect(url_for("dashboard") + "#meetings")


# DELETE MEETING
@app.route("/delete-meeting/<int:meeting_id>", methods=["POST"])
def delete_meeting(meeting_id):
    db = get_db_connection()
    cursor = db.cursor()

    try:
        cursor.execute(
            "DELETE FROM mentorhub_meetings WHERE meeting_id = %s",
            (meeting_id,)
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        cursor.close()
        db.close()

    return redirect(url_for("dashboard") + "#meetings")


# DOWNLOAD STUDENT CSV
@app.route("/export-csv")
def export_csv():
    db = get_db_connection()
    cursor = db.cursor()

    try:
        cursor.execute("""
            SELECT s.student_id, s.student_name, s.department,
                   s.study_year,
                   COALESCE(m.mentor_name, 'Not Assigned')
            FROM students s
            LEFT JOIN mentors m ON s.mentor_id = m.mentor_id
            ORDER BY s.student_id
        """)

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Student ID", "Student Name", "Department",
            "Study Year", "Mentor"
        ])
        writer.writerows(cursor.fetchall())

        return Response(
            "\ufeff" + output.getvalue(),
            mimetype="text/csv",
            headers={
                "Content-Disposition":
                    "attachment; filename=mentorship_students.csv"
            }
        )
    finally:
        cursor.close()
        db.close()


if __name__ == "__main__":
    app.run(debug=True)
