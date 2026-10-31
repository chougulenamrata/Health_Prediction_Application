"""Input validation for patient records.

validate_patient() returns (clean_data, errors). `errors` maps a field name to a
human-readable message, so every problem in a record is reported at once.
"""
import calendar
import re
from datetime import date, datetime

EMAIL_RE = re.compile(
    r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}$"
)
NAME_RE = re.compile(r"^[A-Za-z][A-Za-z .'-]{1,99}$")
NUMBER_RE = re.compile(r"^\d+(\.\d+)?$")
DATE_RE = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")

# Plausible physiological limits (used only to catch typing mistakes).
LIMITS = {
    "glucose": ("Glucose", "mg/dL", 20, 1000),
    "haemoglobin": ("Haemoglobin", "g/dL", 1, 30),
    "cholesterol": ("Cholesterol", "mg/dL", 50, 1000),
}


def parse_dob(raw):
    """Parse dd/mm/yyyy (dots or dashes are accepted as separators).

    Returns (iso_date_string, error_message).
    """
    text = re.sub(r"[.\-]", "/", str(raw or "").strip())
    if not text:
        return None, "Date of birth is required."
    match = DATE_RE.match(text)
    if not match:
        return None, "Date of birth must be in dd/mm/yyyy format."
    day, month, year = (int(g) for g in match.groups())
    if not 1 <= month <= 12:
        return None, f"Month {month} is invalid; it must be between 1 and 12."
    days_in_month = calendar.monthrange(year, month)[1]
    if not 1 <= day <= days_in_month:
        return None, (
            f"Not a real date: {calendar.month_name[month]} {year} "
            f"has only {days_in_month} days."
        )
    dob = date(year, month, day)
    if dob > date.today():
        return None, "Date of birth cannot be in the future."
    if year < 1900:
        return None, "Date of birth must be 1900 or later."
    return dob.isoformat(), None


def format_dob(iso_text):
    return datetime.strptime(iso_text, "%Y-%m-%d").strftime("%d/%m/%Y")


def validate_patient(data):
    clean, errors = {}, {}

    name = re.sub(r"\s+", " ", str(data.get("full_name") or "")).strip()
    if not name:
        errors["full_name"] = "Full name is required."
    elif not NAME_RE.match(name):
        errors["full_name"] = (
            "Full name may contain only letters, spaces, apostrophes, dots and hyphens."
        )
    else:
        clean["full_name"] = name

    dob, dob_error = parse_dob(data.get("dob"))
    if dob_error:
        errors["dob"] = dob_error
    else:
        clean["dob"] = dob

    email = str(data.get("email") or "").strip()
    if not email:
        errors["email"] = "Email address is required."
    elif not EMAIL_RE.match(email):
        errors["email"] = (
            "Invalid email format (expected something like name@example.com)."
        )
    else:
        clean["email"] = email

    for field, (label, unit, low, high) in LIMITS.items():
        raw = str(data.get(field) if data.get(field) is not None else "").strip()
        if not raw:
            errors[field] = f"{label} is required."
        elif not NUMBER_RE.match(raw):
            errors[field] = f"{label} must be a number."
        else:
            value = float(raw)
            if not low <= value <= high:
                errors[field] = f"{label} must be between {low} and {high} {unit}."
            else:
                clean[field] = value

    return clean, errors
