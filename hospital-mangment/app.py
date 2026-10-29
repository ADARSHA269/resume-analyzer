import os
import math
import re
import secrets
import sqlite3
from datetime import date, datetime
from functools import wraps

from flask import Flask, abort, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database import SPECIALIZATIONS, get_db, init_db


app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", secrets.token_hex(32))
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE") == "1",
)
init_db()

PATIENT_GENDERS = {"Female", "Male", "Non-binary", "Prefer not to say"}


@app.before_request
def load_user():
    g.user = None
    if session.get("user_id"):
        g.user = db_connection().execute(
            "SELECT id, name, email, role FROM users WHERE id = ?",
            (session["user_id"],),
        ).fetchone()


@app.teardown_request
def close_db(_error):
    db = getattr(g, "_database", None)
    if db:
        db.close()


def db_connection():
    if not hasattr(g, "_database"):
        g._database = get_db()
    return g._database


@app.template_filter("pretty_date")
def pretty_date(value):
    try:
        return date.fromisoformat(value).strftime("%a, %b %d, %Y")
    except (TypeError, ValueError):
        return value


@app.template_filter("time_label")
def time_label(value):
    try:
        return datetime.strptime(value, "%H:%M").strftime("%I:%M %p").lstrip("0")
    except (TypeError, ValueError):
        return value


@app.context_processor
def template_context():
    return {"today": date.today().isoformat()}


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not g.user:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def roles_required(*roles):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if g.user["role"] not in roles:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator


def get_patient_id():
    patient = db_connection().execute(
        "SELECT id FROM patients WHERE user_id = ?", (g.user["id"],)
    ).fetchone()
    return patient["id"] if patient else None


def valid_email(value):
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value))


@app.route("/")
def home():
    doctors = db_connection().execute(
        """SELECT u.name, s.name AS specialization, d.qualification, d.experience
           FROM doctors d JOIN users u ON u.id = d.user_id
           JOIN specializations s ON s.id = d.specialization_id
           ORDER BY s.name, u.name LIMIT 6"""
    ).fetchall()
    return render_template("home.html", doctors=doctors)


@app.route("/doctors")
def doctors():
    specialization = request.args.get("specialization", "").strip()
    query = """SELECT d.*, u.name, u.email, s.name AS specialization
               FROM doctors d JOIN users u ON u.id = d.user_id
               JOIN specializations s ON s.id = d.specialization_id"""
    params = ()
    if specialization:
        query += " WHERE s.name = ?"
        params = (specialization,)
    query += " ORDER BY s.name, u.name"
    records = db_connection().execute(query, params).fetchall()
    return render_template(
        "doctors.html", doctors=records, specializations=SPECIALIZATIONS,
        selected=specialization,
    )


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        phone = request.form.get("phone", "").strip()
        gender = request.form.get("gender", "").strip()
        history = request.form.get("medical_history", "").strip()
        try:
            age = int(request.form.get("age", ""))
        except ValueError:
            age = -1
        if (not name or len(name) > 100 or not valid_email(email) or len(email) > 254
                or len(password) < 8 or not phone or len(phone) > 30
                or gender not in PATIENT_GENDERS or len(history) > 1000):
            flash("Complete all required fields. Passwords must be at least 8 characters.", "danger")
        elif not 0 <= age <= 120:
            flash("Enter a valid age between 0 and 120.", "danger")
        else:
            db = db_connection()
            try:
                cursor = db.execute(
                    "INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, 'patient')",
                    (name, email, generate_password_hash(password)),
                )
                db.execute(
                    """INSERT INTO patients (user_id, age, gender, phone, medical_history)
                       VALUES (?, ?, ?, ?, ?)""",
                    (cursor.lastrowid, age, gender, phone, history),
                )
                db.commit()
                flash("Your patient account is ready. Please log in.", "success")
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                db.rollback()
                flash("An account with that email already exists.", "danger")
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", "")
        user = db_connection().execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchone()
        if user and check_password_hash(user["password_hash"], password) and user["role"] == role:
            session.clear()
            session["user_id"] = user["id"]
            return redirect(url_for("dashboard"))
        flash("Email, password, or account type is incorrect.", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("home"))


@app.route("/dashboard")
@login_required
def dashboard():
    db = db_connection()
    if g.user["role"] == "admin":
        counts = {
            "doctors": db.execute("SELECT COUNT(*) FROM doctors").fetchone()[0],
            "patients": db.execute("SELECT COUNT(*) FROM patients").fetchone()[0],
            "appointments": db.execute("SELECT COUNT(*) FROM appointments").fetchone()[0],
        }
        appointments = db.execute(
            """SELECT a.*, puser.name AS patient_name, duser.name AS doctor_name,
                      s.name AS specialization
               FROM appointments a
               JOIN patients p ON p.id = a.patient_id
               JOIN users puser ON puser.id = p.user_id
               JOIN doctors d ON d.id = a.doctor_id
               JOIN users duser ON duser.id = d.user_id
               JOIN specializations s ON s.id = d.specialization_id
               WHERE a.appointment_date = ? ORDER BY a.time_slot""",
            (date.today().isoformat(),),
        ).fetchall()
        return render_template("dashboard.html", counts=counts, appointments=appointments)
    if g.user["role"] == "doctor":
        doctor = db.execute("SELECT id FROM doctors WHERE user_id = ?", (g.user["id"],)).fetchone()
        if not doctor:
            abort(403)
        appointments = db.execute(
            """SELECT a.*, u.name AS patient_name, p.age, p.gender, p.phone, p.medical_history
               FROM appointments a JOIN patients p ON p.id = a.patient_id
               JOIN users u ON u.id = p.user_id WHERE a.doctor_id = ?
               ORDER BY a.appointment_date DESC, a.time_slot""",
            (doctor["id"],),
        ).fetchall()
        slots = db.execute(
            """SELECT * FROM doctor_availability WHERE doctor_id = ? AND appointment_date >= ?
               ORDER BY appointment_date, time_slot""",
            (doctor["id"], date.today().isoformat()),
        ).fetchall()
        return render_template("dashboard.html", appointments=appointments, slots=slots)
    return redirect(url_for("my_appointments"))


@app.route("/book", methods=["GET", "POST"])
@roles_required("patient")
def book_appointment():
    db = db_connection()
    if request.method == "POST":
        doctor_id = request.form.get("doctor_id", type=int)
        availability_id = request.form.get("availability_id", type=int)
        patient_id = get_patient_id()
        try:
            db.execute("BEGIN IMMEDIATE")
            slot = db.execute(
                """SELECT av.*, d.id AS doctor_id FROM doctor_availability av
                   JOIN doctors d ON d.id = av.doctor_id WHERE av.id = ? AND d.id = ?""",
                (availability_id, doctor_id),
            ).fetchone()
            now = datetime.now()
            if (not slot or slot["appointment_date"] < now.date().isoformat()
                    or (slot["appointment_date"] == now.date().isoformat()
                        and slot["time_slot"] <= now.strftime("%H:%M"))):
                db.rollback()
                flash("That appointment slot is no longer available.", "danger")
                return redirect(url_for("book_appointment"))
            occupied = db.execute(
                """SELECT id FROM appointments WHERE availability_id = ?
                   AND status != 'Cancelled'""",
                (availability_id,),
            ).fetchone()
            if occupied:
                db.rollback()
                flash("Sorry, that slot was just booked. Please choose another.", "danger")
                return redirect(url_for("book_appointment"))
            db.execute(
                """INSERT INTO appointments
                   (appointment_code, patient_id, doctor_id, availability_id, appointment_date, time_slot)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (secrets.token_hex(6).upper(), patient_id, doctor_id, availability_id,
                 slot["appointment_date"], slot["time_slot"]),
            )
            db.commit()
            flash("Appointment booked successfully. It is pending confirmation.", "success")
            return redirect(url_for("my_appointments"))
        except sqlite3.IntegrityError:
            db.rollback()
            flash("That slot is no longer available. Please choose another.", "danger")
            return redirect(url_for("book_appointment"))

    specialization = request.args.get("specialization", "").strip()
    doctor_id = request.args.get("doctor_id", type=int)
    doctor_query = """SELECT d.id, u.name, s.name AS specialization FROM doctors d
                      JOIN users u ON u.id = d.user_id JOIN specializations s ON s.id = d.specialization_id"""
    doctor_params = ()
    if specialization:
        doctor_query += " WHERE s.name = ?"
        doctor_params = (specialization,)
    doctor_query += " ORDER BY s.name, u.name"
    doctors = db.execute(doctor_query, doctor_params).fetchall()
    doctor_ids = {doctor["id"] for doctor in doctors}
    selected_doctor = doctor_id if doctor_id in doctor_ids else (
        doctors[0]["id"] if doctors else None
    )
    available_slots = []
    if selected_doctor:
        available_slots = db.execute(
            """SELECT av.* FROM doctor_availability av
               WHERE av.doctor_id = ?
               AND (av.appointment_date > ? OR (av.appointment_date = ? AND av.time_slot > ?))
               AND NOT EXISTS (SELECT 1 FROM appointments a
                   WHERE a.availability_id = av.id AND a.status != 'Cancelled')
               ORDER BY av.appointment_date, av.time_slot""",
            (selected_doctor, date.today().isoformat(), date.today().isoformat(),
             datetime.now().strftime("%H:%M")),
        ).fetchall()
    return render_template(
        "book.html", doctors=doctors, slots=available_slots,
        selected_doctor=selected_doctor, specializations=SPECIALIZATIONS,
        selected_specialization=specialization,
    )


@app.route("/appointments")
@roles_required("patient")
def my_appointments():
    appointments = db_connection().execute(
        """SELECT a.*, u.name AS doctor_name, s.name AS specialization
           FROM appointments a JOIN doctors d ON d.id = a.doctor_id
           JOIN users u ON u.id = d.user_id
           JOIN specializations s ON s.id = d.specialization_id
           WHERE a.patient_id = ? ORDER BY a.appointment_date DESC, a.time_slot""",
        (get_patient_id(),),
    ).fetchall()
    return render_template("appointments.html", appointments=appointments, owner="patient")


@app.route("/appointments/<int:appointment_id>/cancel", methods=["POST"])
@roles_required("patient", "admin")
def cancel_appointment(appointment_id):
    db = db_connection()
    if g.user["role"] == "patient":
        result = db.execute(
            """UPDATE appointments SET status = 'Cancelled' WHERE id = ?
               AND patient_id = ? AND status IN ('Pending', 'Confirmed')""",
            (appointment_id, get_patient_id()),
        )
    else:
        result = db.execute(
            """UPDATE appointments SET status = 'Cancelled' WHERE id = ?
               AND status IN ('Pending', 'Confirmed')""",
            (appointment_id,),
        )
    db.commit()
    flash("Appointment cancelled." if result.rowcount else "That appointment could not be cancelled.", "info")
    return redirect(url_for("dashboard") if g.user["role"] == "admin" else url_for("my_appointments"))


@app.route("/appointments/<int:appointment_id>/status", methods=["POST"])
@roles_required("doctor", "admin")
def update_appointment_status(appointment_id):
    status = request.form.get("status", "")
    allowed = {"Confirmed", "Completed", "Cancelled"} if g.user["role"] == "doctor" else {"Confirmed", "Cancelled"}
    db = db_connection()
    appointment = db.execute(
        """SELECT a.id, a.status FROM appointments a JOIN doctors d ON d.id = a.doctor_id
           WHERE a.id = ? AND (? = 'admin' OR d.user_id = ?)""",
        (appointment_id, g.user["role"], g.user["id"]),
    ).fetchone()
    if not appointment:
        abort(403)
    if appointment["status"] == "Pending":
        transitions = {"Confirmed", "Cancelled"}
    elif appointment["status"] == "Confirmed":
        transitions = {"Cancelled"}
        if g.user["role"] == "doctor":
            transitions.add("Completed")
    else:
        transitions = set()
    if status not in allowed or status not in transitions:
        abort(400)
    db.execute(
        "UPDATE appointments SET status = ? WHERE id = ?",
        (status, appointment_id),
    )
    db.commit()
    flash("Appointment status updated.", "success")
    return redirect(url_for("dashboard"))


@app.route("/doctor/availability", methods=["POST"])
@roles_required("doctor")
def add_availability():
    db = db_connection()
    doctor = db.execute("SELECT id FROM doctors WHERE user_id = ?", (g.user["id"],)).fetchone()
    appointment_date = request.form.get("appointment_date", "")
    time_slot = request.form.get("time_slot", "")
    try:
        parsed_date = date.fromisoformat(appointment_date)
    except ValueError:
        parsed_date = date.min
    if not doctor or parsed_date < date.today() or time_slot not in {
        "09:00", "10:00", "11:00", "12:00", "13:00", "14:00", "15:00", "16:00"
    }:
        flash("Choose a valid future date and an available time.", "danger")
    elif (parsed_date == date.today()
          and time_slot <= datetime.now().strftime("%H:%M")):
        flash("Choose a time later than now.", "danger")
    else:
        try:
            db.execute(
                """INSERT INTO doctor_availability (doctor_id, appointment_date, time_slot)
                   VALUES (?, ?, ?)""",
                (doctor["id"], appointment_date, time_slot),
            )
            db.commit()
            flash("Availability added.", "success")
        except sqlite3.IntegrityError:
            flash("That availability slot already exists.", "warning")
    return redirect(url_for("dashboard"))


@app.route("/doctor/availability/<int:slot_id>/delete", methods=["POST"])
@roles_required("doctor")
def delete_availability(slot_id):
    db = db_connection()
    doctor = db.execute("SELECT id FROM doctors WHERE user_id = ?", (g.user["id"],)).fetchone()
    if doctor:
        db.execute(
            """DELETE FROM doctor_availability WHERE id = ? AND doctor_id = ?
               AND NOT EXISTS (SELECT 1 FROM appointments WHERE availability_id = doctor_availability.id
                   AND status != 'Cancelled')""",
            (slot_id, doctor["id"]),
        )
        db.commit()
    flash("Availability removed if it had no active booking.", "info")
    return redirect(url_for("dashboard"))


def doctor_form_values():
    values = {}
    for field in ("name", "email", "qualification", "phone", "timings", "specialization"):
        values[field] = request.form.get(field, "").strip()
    for field in ("experience", "fee"):
        try:
            values[field] = float(request.form.get(field, "")) if field == "fee" else int(request.form.get(field, ""))
        except ValueError:
            values[field] = -1
    values["password"] = request.form.get("password", "")
    return values


@app.route("/admin/doctors", methods=["GET", "POST"])
@roles_required("admin")
def manage_doctors():
    db = db_connection()
    if request.method == "POST":
        values = doctor_form_values()
        specialization = db.execute(
            "SELECT id FROM specializations WHERE name = ?", (values["specialization"],)
        ).fetchone()
        if (not all(values[key] for key in ("name", "email", "qualification", "phone", "timings"))
                or len(values["name"]) > 100 or not valid_email(values["email"])
                or len(values["email"]) > 254 or len(values["qualification"]) > 100
                or len(values["phone"]) > 30 or len(values["timings"]) > 100
                or not specialization or values["experience"] < 0 or not math.isfinite(values["fee"])
                or values["fee"] < 0
                or len(values["password"]) < 8):
            flash("Provide valid doctor details; password must be at least 8 characters.", "danger")
        else:
            try:
                cursor = db.execute(
                    """INSERT INTO users (name, email, password_hash, role)
                       VALUES (?, ?, ?, 'doctor')""",
                    (values["name"], values["email"].lower(), generate_password_hash(values["password"])),
                )
                db.execute(
                    """INSERT INTO doctors
                       (user_id, specialization_id, qualification, experience, fee, phone, timings)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (cursor.lastrowid, specialization["id"], values["qualification"], values["experience"],
                     values["fee"], values["phone"], values["timings"]),
                )
                db.commit()
                flash("Doctor profile created.", "success")
                return redirect(url_for("manage_doctors"))
            except sqlite3.IntegrityError:
                db.rollback()
                flash("That email address is already in use.", "danger")
    records = db.execute(
        """SELECT d.*, u.name, u.email, s.name AS specialization FROM doctors d
           JOIN users u ON u.id = d.user_id JOIN specializations s ON s.id = d.specialization_id
           ORDER BY u.name"""
    ).fetchall()
    return render_template("manage_doctors.html", doctors=records, specializations=SPECIALIZATIONS)


@app.route("/admin/doctors/<int:doctor_id>/edit", methods=["GET", "POST"])
@roles_required("admin")
def edit_doctor(doctor_id):
    db = db_connection()
    doctor = db.execute(
        """SELECT d.*, u.name, u.email, s.name AS specialization FROM doctors d
           JOIN users u ON u.id = d.user_id JOIN specializations s ON s.id = d.specialization_id
           WHERE d.id = ?""",
        (doctor_id,),
    ).fetchone()
    if not doctor:
        abort(404)
    if request.method == "POST":
        values = doctor_form_values()
        specialization = db.execute(
            "SELECT id FROM specializations WHERE name = ?", (values["specialization"],)
        ).fetchone()
        if (not all(values[key] for key in ("name", "email", "qualification", "phone", "timings"))
                or len(values["name"]) > 100 or not valid_email(values["email"])
                or len(values["email"]) > 254 or len(values["qualification"]) > 100
                or len(values["phone"]) > 30 or len(values["timings"]) > 100
                or not specialization or values["experience"] < 0 or not math.isfinite(values["fee"])
                or values["fee"] < 0):
            flash("Please provide valid doctor details.", "danger")
        else:
            try:
                db.execute("UPDATE users SET name = ?, email = ? WHERE id = ?",
                           (values["name"], values["email"].lower(), doctor["user_id"]))
                db.execute(
                    """UPDATE doctors SET specialization_id = ?, qualification = ?, experience = ?,
                       fee = ?, phone = ?, timings = ? WHERE id = ?""",
                    (specialization["id"], values["qualification"], values["experience"],
                     values["fee"], values["phone"], values["timings"], doctor_id),
                )
                db.commit()
                flash("Doctor profile updated.", "success")
                return redirect(url_for("manage_doctors"))
            except sqlite3.IntegrityError:
                db.rollback()
                flash("That email address is already in use.", "danger")
    return render_template("edit_doctor.html", doctor=doctor, specializations=SPECIALIZATIONS)


@app.route("/admin/doctors/<int:doctor_id>/delete", methods=["POST"])
@roles_required("admin")
def delete_doctor(doctor_id):
    db = db_connection()
    doctor = db.execute("SELECT user_id FROM doctors WHERE id = ?", (doctor_id,)).fetchone()
    if doctor:
        appointment_history = db.execute(
            "SELECT COUNT(*) FROM appointments WHERE doctor_id = ?",
            (doctor_id,),
        ).fetchone()[0]
        if appointment_history:
            flash("This doctor has appointment history and cannot be deleted.", "warning")
        else:
            db.execute("DELETE FROM doctors WHERE id = ?", (doctor_id,))
            db.execute("DELETE FROM users WHERE id = ?", (doctor["user_id"],))
            db.commit()
            flash("Doctor profile deleted.", "success")
    return redirect(url_for("manage_doctors"))


@app.route("/admin/patients")
@roles_required("admin")
def manage_patients():
    patients = db_connection().execute(
        """SELECT p.*, u.name, u.email, u.created_at FROM patients p
           JOIN users u ON u.id = p.user_id ORDER BY u.name"""
    ).fetchall()
    return render_template("patients.html", patients=patients)


@app.route("/admin/patients/<int:patient_id>/edit", methods=["GET", "POST"])
@roles_required("admin")
def edit_patient(patient_id):
    db = db_connection()
    patient = db.execute(
        """SELECT p.*, u.name, u.email FROM patients p
           JOIN users u ON u.id = p.user_id WHERE p.id = ?""",
        (patient_id,),
    ).fetchone()
    if not patient:
        abort(404)
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        gender = request.form.get("gender", "").strip()
        history = request.form.get("medical_history", "").strip()
        try:
            age = int(request.form.get("age", ""))
        except ValueError:
            age = -1
        if (not name or len(name) > 100 or not valid_email(email) or len(email) > 254
                or not phone or len(phone) > 30 or gender not in PATIENT_GENDERS
                or len(history) > 1000 or not 0 <= age <= 120):
            flash("Please provide valid patient details.", "danger")
        else:
            try:
                db.execute(
                    "UPDATE users SET name = ?, email = ? WHERE id = ?",
                    (name, email, patient["user_id"]),
                )
                db.execute(
                    """UPDATE patients SET age = ?, gender = ?, phone = ?, medical_history = ?
                       WHERE id = ?""",
                    (age, gender, phone, history, patient_id),
                )
                db.commit()
                flash("Patient record updated.", "success")
                return redirect(url_for("manage_patients"))
            except sqlite3.IntegrityError:
                db.rollback()
                flash("That email address is already in use.", "danger")
    return render_template("edit_patient.html", patient=patient)


@app.route("/admin/appointments")
@roles_required("admin")
def manage_appointments():
    appointments = db_connection().execute(
        """SELECT a.*, puser.name AS patient_name, duser.name AS doctor_name,
                  s.name AS specialization
           FROM appointments a
           JOIN patients p ON p.id = a.patient_id
           JOIN users puser ON puser.id = p.user_id
           JOIN doctors d ON d.id = a.doctor_id
           JOIN users duser ON duser.id = d.user_id
           JOIN specializations s ON s.id = d.specialization_id
           ORDER BY a.appointment_date DESC, a.time_slot"""
    ).fetchall()
    return render_template("admin_appointments.html", appointments=appointments)


@app.errorhandler(403)
def forbidden(_error):
    return render_template("error.html", code=403, message="You do not have permission to view this page."), 403


@app.errorhandler(404)
def not_found(_error):
    return render_template("error.html", code=404, message="The page or record could not be found."), 404


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
