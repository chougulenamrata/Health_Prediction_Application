"""External AI integration (Google Gemini REST API).

The API key is read from the GEMINI_API_KEY environment variable (see .env.example)
and is sent in a request header, so it never appears in URLs, logs or the repository.
"""
import os
from datetime import date

import requests
from dotenv import load_dotenv

load_dotenv()

API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
TIMEOUT_SECONDS = 30


class AIServiceError(Exception):
    """Raised when the AI prediction could not be obtained."""


def _age(dob_iso):
    born = date.fromisoformat(dob_iso)
    today = date.today()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


def build_prompt(patient):
    return (
        "You are a clinical decision-support assistant giving screening-level information.\n"
        f"Patient age: {_age(patient['dob'])} years (sex not provided).\n"
        f"Fasting glucose: {patient['glucose']} mg/dL (normal 70-99, prediabetes 100-125, diabetes >=126)\n"
        f"Haemoglobin: {patient['haemoglobin']} g/dL (adult normal about 12-17.5)\n"
        f"Total cholesterol: {patient['cholesterol']} mg/dL (desirable <200, borderline 200-239, high >=240)\n\n"
        "Predict the most likely health condition or disease risk from these values. "
        "Reply in plain text, at most 35 words, in this form: "
        "'<possible condition(s)> - <Low/Moderate/High> risk. <one-sentence reason>.' "
        "Do not add markdown or disclaimers."
    )


def predict_without_gemini(patient):
    """Provide a deterministic screening result when no Gemini key is configured."""
    glucose = float(patient["glucose"])
    haemoglobin = float(patient["haemoglobin"])
    cholesterol = float(patient["cholesterol"])

    glucose_risk = "High" if glucose >= 126 else "Moderate" if glucose >= 100 else "Low"
    haemoglobin_risk = "High" if haemoglobin < 10 else "Moderate" if haemoglobin < 12 else "Low"
    cholesterol_risk = "High" if cholesterol >= 240 else "Moderate" if cholesterol >= 200 else "Low"
    risk_levels = {"Low": 0, "Moderate": 1, "High": 2}
    overall = max((glucose_risk, haemoglobin_risk, cholesterol_risk), key=risk_levels.get)

    concerns = []
    if glucose >= 126:
        concerns.append("possible diabetes range")
    elif glucose >= 100:
        concerns.append("prediabetes-range glucose")
    if haemoglobin < 12:
        concerns.append("possible low haemoglobin")
    if cholesterol >= 240:
        concerns.append("high cholesterol")
    elif cholesterol >= 200:
        concerns.append("borderline cholesterol")

    condition = " and ".join(concerns) if concerns else "no abnormal screening flags"
    return f"{condition.title()} - {overall} risk. Screening based on glucose, haemoglobin, and cholesterol values."


def predict_health_risk(patient):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return predict_without_gemini(patient)
    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

    payload = {
        "contents": [{"parts": [{"text": build_prompt(patient)}]}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 150,
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }
    try:
        response = requests.post(
            API_URL.format(model=model),
            headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
            json=payload,
            timeout=TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise AIServiceError(f"Could not reach the AI service ({type(exc).__name__}).") from exc

    if response.status_code != 200:
        raise AIServiceError(f"AI service returned HTTP {response.status_code}.")

    try:
        text = response.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (KeyError, IndexError, ValueError) as exc:
        raise AIServiceError("AI service returned an unexpected response.") from exc
    if not text:
        raise AIServiceError("AI service returned an empty response.")
    return text
