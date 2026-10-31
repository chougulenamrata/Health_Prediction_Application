"""SQLite persistence layer."""
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(os.environ.get("HEALTH_DB_PATH") or Path(__file__).with_name("patients.db"))

FIELDS = ("full_name", "dob", "email", "glucose", "haemoglobin", "cholesterol")


@contextmanager
def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with connect() as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS patients (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name   TEXT NOT NULL,
                dob         TEXT NOT NULL,          -- stored as YYYY-MM-DD
                email       TEXT NOT NULL,
                glucose     REAL NOT NULL,
                haemoglobin REAL NOT NULL,
                cholesterol REAL NOT NULL,
                remarks     TEXT,
                created_at  TEXT DEFAULT CURRENT_TIMESTAMP
            )"""
        )
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_patients_email "
            "ON patients(email COLLATE NOCASE)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS rejected_records ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "full_name TEXT, dob TEXT, email TEXT, glucose TEXT, haemoglobin TEXT, "
            "cholesterol TEXT, errors TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP)"
        )


def list_patients():
    with connect() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM patients ORDER BY id")]


def get_patient(patient_id):
    with connect() as conn:
        row = conn.execute("SELECT * FROM patients WHERE id = ?", (patient_id,)).fetchone()
        return dict(row) if row else None


def find_duplicates(clean, exclude_id=None):
    """Return {field: message} if the email or the name + date of birth already exist."""
    exclude_id = exclude_id or -1
    errors = {}
    with connect() as conn:
        if conn.execute(
            "SELECT 1 FROM patients WHERE email = ? COLLATE NOCASE AND id != ?",
            (clean["email"], exclude_id),
        ).fetchone():
            errors["email"] = "Duplicate record: this email address is already registered."
        if conn.execute(
            "SELECT 1 FROM patients WHERE full_name = ? COLLATE NOCASE AND dob = ? AND id != ?",
            (clean["full_name"], clean["dob"], exclude_id),
        ).fetchone():
            errors["full_name"] = "Duplicate record: this patient (same name and date of birth) already exists."
    return errors


def create_patient(clean):
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO patients (full_name, dob, email, glucose, haemoglobin, cholesterol) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            tuple(clean[f] for f in FIELDS),
        )
        return cur.lastrowid


def update_patient(patient_id, clean, remarks):
    with connect() as conn:
        conn.execute(
            "UPDATE patients SET full_name=?, dob=?, email=?, glucose=?, haemoglobin=?, "
            "cholesterol=?, remarks=? WHERE id=?",
            (*[clean[f] for f in FIELDS], remarks, patient_id),
        )


def set_remarks(patient_id, remarks):
    with connect() as conn:
        conn.execute("UPDATE patients SET remarks = ? WHERE id = ?", (remarks, patient_id))


def create_rejected_record(submitted, errors):
    import json
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO rejected_records (full_name, dob, email, glucose, haemoglobin, cholesterol, errors) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                str(submitted.get("full_name") or ""),
                str(submitted.get("dob") or ""),
                str(submitted.get("email") or ""),
                str(submitted.get("glucose") or ""),
                str(submitted.get("haemoglobin") or ""),
                str(submitted.get("cholesterol") or ""),
                json.dumps(errors, ensure_ascii=False),
            ),
        )
        return cur.lastrowid


def list_rejected_records():
    import json
    with connect() as conn:
        records = [dict(row) for row in conn.execute(
            "SELECT * FROM rejected_records ORDER BY id"
        )]
    for record in records:
        record["errors"] = json.loads(record["errors"])
    return records


def delete_patient(patient_id):
    with connect() as conn:
        return conn.execute("DELETE FROM patients WHERE id = ?", (patient_id,)).rowcount > 0
