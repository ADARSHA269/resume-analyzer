import os
import tempfile
import unittest

import database
from werkzeug.security import generate_password_hash


_test_directory = tempfile.TemporaryDirectory()
database.DATABASE = os.path.join(_test_directory.name, "test-hospital.db")

import app as hospital_app


class HospitalAppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        hospital_app.app.config.update(TESTING=True, SECRET_KEY="test-secret")
        cls.db = database.get_db()
        cls.doctor = cls.db.execute("SELECT id FROM doctors LIMIT 1").fetchone()
        cls.slot = cls.db.execute(
            """SELECT id, appointment_date FROM doctor_availability
               WHERE doctor_id = ? AND appointment_date >= date('now')
               ORDER BY appointment_date, time_slot LIMIT 1""",
            (cls.doctor["id"],),
        ).fetchone()
        cls.admin_id = cls.db.execute(
            """INSERT INTO users (name, email, password_hash, role)
               VALUES (?, ?, ?, 'admin')""",
            ("Test Admin", "test-admin@example.test", generate_password_hash("admin-pass-123")),
        ).lastrowid
        cls.db.commit()
        cls.db.close()

    def setUp(self):
        self.client = hospital_app.app.test_client()

    def register_patient(self, email):
        self.client.post(
            "/register",
            data={
                "name": "Test Patient",
                "email": email,
                "password": "patient-pass-123",
                "phone": "555-0199",
                "age": "30",
                "gender": "Prefer not to say",
                "medical_history": "",
            },
            follow_redirects=True,
        )
        return self.client.post(
            "/login",
            data={"email": email, "password": "patient-pass-123", "role": "patient"},
            follow_redirects=True,
        )

    def test_booking_slot_cannot_be_double_booked(self):
        self.assertIsNotNone(self.slot)
        self.register_patient("one@example.test")
        self.assertEqual(self.client.get("/book").status_code, 200)
        response = self.client.post(
            "/book",
            data={"doctor_id": self.doctor["id"], "availability_id": self.slot["id"]},
            follow_redirects=True,
        )
        self.assertIn(b"Appointment booked successfully", response.data)
        self.client.get("/logout")
        self.register_patient("two@example.test")
        response = self.client.post(
            "/book",
            data={"doctor_id": self.doctor["id"], "availability_id": self.slot["id"]},
            follow_redirects=True,
        )
        self.assertIn(b"slot was just booked", response.data)
        db = database.get_db()
        first_appointment_id = db.execute(
            "SELECT id FROM appointments WHERE patient_id = (SELECT p.id FROM patients p JOIN users u ON u.id = p.user_id WHERE u.email = ?)",
            ("one@example.test",),
        ).fetchone()["id"]
        db.close()
        self.client.get("/logout")
        self.client.post(
            "/login",
            data={"email": "one@example.test", "password": "patient-pass-123", "role": "patient"},
        )
        self.client.post(f"/appointments/{first_appointment_id}/cancel")
        self.client.get("/logout")
        self.client.post(
            "/login",
            data={"email": "two@example.test", "password": "patient-pass-123", "role": "patient"},
        )
        response = self.client.post(
            "/book",
            data={"doctor_id": self.doctor["id"], "availability_id": self.slot["id"]},
            follow_redirects=True,
        )
        self.assertIn(b"Appointment booked successfully", response.data)
        db = database.get_db()
        count = db.execute(
            """SELECT COUNT(*) FROM appointments WHERE availability_id = ?
               AND status != 'Cancelled'""",
            (self.slot["id"],),
        ).fetchone()[0]
        db.close()
        self.assertEqual(count, 1)

    def test_public_and_admin_pages_render(self):
        for path in ("/", "/doctors", "/login", "/register"):
            self.assertEqual(self.client.get(path).status_code, 200)
        self.client.post(
            "/login",
            data={"email": "test-admin@example.test", "password": "admin-pass-123", "role": "admin"},
        )
        for path in ("/dashboard", "/admin/doctors", "/admin/patients", "/admin/appointments"):
            self.assertEqual(self.client.get(path).status_code, 200)
        self.client.get("/logout")
        self.client.post(
            "/login",
            data={
                "email": "asha.rao@hospital.local",
                "password": "doctor123",
                "role": "doctor",
            },
        )
        self.assertEqual(self.client.get("/dashboard").status_code, 200)

    def test_role_is_required_to_access_admin_pages(self):
        response = self.client.get("/admin/doctors")
        self.assertEqual(response.status_code, 302)


if __name__ == "__main__":
    unittest.main()
