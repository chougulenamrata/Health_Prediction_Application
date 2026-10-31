"""Health Prediction Application - Flask backend (REST API + single-page UI)."""
from flask import Flask, jsonify, render_template, request

import database as db
from ai_service import AIServiceError, predict_health_risk
from validators import format_dob, validate_patient

app = Flask(__name__)
db.init_db()

HEALTH_FIELDS = ("dob", "glucose", "haemoglobin", "cholesterol")


def serialize(row):
    patient = dict(row)
    patient["dob"] = format_dob(patient["dob"])
    return patient


def run_ai(patient_id, clean):
    """Call the AI API and store the result. Returns (remarks, warning)."""
    try:
        remarks = predict_health_risk(clean)
    except AIServiceError as exc:
        return None, f"Record saved, but the AI prediction failed: {exc}"
    db.set_remarks(patient_id, remarks)
    return remarks, None


def read_json():
    return request.get_json(silent=True) or {}


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/patients")
def list_patients():
    return jsonify([serialize(p) for p in db.list_patients()])


@app.get("/api/rejected")
def list_rejected():
    return jsonify(db.list_rejected_records())


@app.post("/api/patients")
def create_patient():
    submitted = read_json()
    clean, errors = validate_patient(submitted)
    if errors:
        db.create_rejected_record(submitted, errors)
        return jsonify({"errors": errors}), 400
    duplicates = db.find_duplicates(clean)
    if duplicates:
        db.create_rejected_record(submitted, duplicates)
        return jsonify({"errors": duplicates}), 409

    patient_id = db.create_patient(clean)
    _, warning = run_ai(patient_id, clean)
    return jsonify({"patient": serialize(db.get_patient(patient_id)), "warning": warning}), 201


@app.put("/api/patients/<int:patient_id>")
def update_patient(patient_id):
    existing = db.get_patient(patient_id)
    if not existing:
        return jsonify({"errors": {"_": "Record not found."}}), 404

    submitted = read_json()
    clean, errors = validate_patient(submitted)
    if errors:
        db.create_rejected_record(submitted, errors)
        return jsonify({"errors": errors}), 400
    duplicates = db.find_duplicates(clean, exclude_id=patient_id)
    if duplicates:
        db.create_rejected_record(submitted, duplicates)
        return jsonify({"errors": duplicates}), 409

    # Only re-run the AI when something it depends on has changed.
    health_changed = any(clean[f] != existing[f] for f in HEALTH_FIELDS)
    db.update_patient(patient_id, clean, None if health_changed else existing["remarks"])
    warning = None
    if health_changed:
        _, warning = run_ai(patient_id, clean)
    return jsonify({"patient": serialize(db.get_patient(patient_id)), "warning": warning})


@app.post("/api/patients/<int:patient_id>/remarks")
def regenerate_remarks(patient_id):
    patient = db.get_patient(patient_id)
    if not patient:
        return jsonify({"errors": {"_": "Record not found."}}), 404
    _, warning = run_ai(patient_id, patient)
    return jsonify({"patient": serialize(db.get_patient(patient_id)), "warning": warning})


@app.delete("/api/patients/<int:patient_id>")
def delete_patient(patient_id):
    if not db.delete_patient(patient_id):
        return jsonify({"errors": {"_": "Record not found."}}), 404
    return jsonify({"deleted": patient_id})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
