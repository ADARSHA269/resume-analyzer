import os
import sqlite3
from datetime import date, timedelta

from werkzeug.security import generate_password_hash


DATABASE = os.path.join(os.path.dirname(__file__), "hospital.db")

SPECIALIZATIONS = [
    "Cardiology",
    "Dermatology",
    "Neurology",
    "Orthopedics",
    "Pediatrics",
    "General Medicine",
    "Gynecology",
    "Ophthalmology",
    "ENT",
    "Dentistry",
]


def get_db():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db():
    db = get_db()
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('admin', 'doctor', 'patient')),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS specializations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        );
        CREATE TABLE IF NOT EXISTS doctors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE REFERENCES users(id) ON DELETE SET NULL,
            specialization_id INTEGER NOT NULL REFERENCES specializations(id),
            qualification TEXT NOT NULL,
            experience INTEGER NOT NULL CHECK (experience >= 0),
            fee REAL NOT NULL CHECK (fee >= 0),
            phone TEXT NOT NULL,
            timings TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
            age INTEGER NOT NULL CHECK (age BETWEEN 0 AND 120),
            gender TEXT NOT NULL,
            phone TEXT NOT NULL,
            medical_history TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS doctor_availability (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doctor_id INTEGER NOT NULL REFERENCES doctors(id) ON DELETE CASCADE,
            appointment_date TEXT NOT NULL,
            time_slot TEXT NOT NULL,
            UNIQUE (doctor_id, appointment_date, time_slot)
        );
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            appointment_code TEXT NOT NULL UNIQUE,
            patient_id INTEGER NOT NULL REFERENCES patients(id),
            doctor_id INTEGER NOT NULL REFERENCES doctors(id),
            availability_id INTEGER NOT NULL REFERENCES doctor_availability(id),
            appointment_date TEXT NOT NULL,
            time_slot TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Pending'
                CHECK (status IN ('Pending', 'Confirmed', 'Completed', 'Cancelled')),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE UNIQUE INDEX IF NOT EXISTS one_active_booking_per_slot
            ON appointments(availability_id) WHERE status != 'Cancelled';
        """
    )

    for specialization in SPECIALIZATIONS:
        db.execute(
            "INSERT OR IGNORE INTO specializations (name) VALUES (?)",
            (specialization,),
        )

    admin_email = os.environ.get("ADMIN_EMAIL", "admin@hospital.local")
    admin_password = os.environ.get("ADMIN_PASSWORD", "admin123")
    db.execute(
        """INSERT OR IGNORE INTO users (name, email, password_hash, role)
           VALUES (?, ?, ?, 'admin')""",
        ("Hospital Admin", admin_email, generate_password_hash(admin_password)),
    )

    samples = [
        ("Dr. Asha Rao", "asha.rao@hospital.local", "Cardiology", "MBBS, MD", 12, 700, "555-0101"),
        ("Dr. Daniel Kim", "daniel.kim@hospital.local", "Dermatology", "MBBS, DDVL", 8, 500, "555-0102"),
        ("Dr. Maya Patel", "maya.patel@hospital.local", "Pediatrics", "MBBS, DCH", 10, 600, "555-0103"),
        ("Dr. Ethan Lee", "ethan.lee@hospital.local", "General Medicine", "MBBS, MD", 15, 450, "555-0104"),
        ("Dr. Sofia Ahmed", "sofia.ahmed@hospital.local", "Orthopedics", "MBBS, MS", 9, 650, "555-0105"),
    ]
    for name, email, specialization, qualification, experience, fee, phone in samples:
        db.execute(
            """INSERT OR IGNORE INTO users (name, email, password_hash, role)
               VALUES (?, ?, ?, 'doctor')""",
            (name, email, generate_password_hash("doctor123")),
        )
        user = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        spec = db.execute(
            "SELECT id FROM specializations WHERE name = ?", (specialization,)
        ).fetchone()
        db.execute(
            """INSERT OR IGNORE INTO doctors
               (user_id, specialization_id, qualification, experience, fee, phone, timings)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user["id"], spec["id"], qualification, experience, fee, phone, "Mon-Fri, 9:00 AM - 1:00 PM"),
        )

    slots = ["09:00", "10:00", "11:00", "12:00"]
    for doctor in db.execute("SELECT id FROM doctors").fetchall():
        for offset in range(1, 15):
            slot_date = date.today() + timedelta(days=offset)
            if slot_date.weekday() < 5:
                for slot in slots:
                    db.execute(
                        """INSERT OR IGNORE INTO doctor_availability
                           (doctor_id, appointment_date, time_slot) VALUES (?, ?, ?)""",
                        (doctor["id"], slot_date.isoformat(), slot),
                    )

    db.commit()
    db.close()
