# Health Prediction Application

A Flask + SQLite web app to manage patient blood-test records (full name, date of birth, email,
glucose, haemoglobin, cholesterol). When a valid record is saved, the values are sent to the
Google Gemini API, which predicts a possible condition / risk level. The result is stored in the
**Remarks** column.

> Remarks are AI-generated screening information, not a medical diagnosis.

## Features
- Create, Read, Update, Delete patient records (single-page Bootstrap UI)
- Server-side validation (all errors for a record are reported together):
  - full name: letters, spaces, `'` `.` `-`
  - date of birth: `dd/mm/yyyy`, must be a real calendar date and not in the future
    (`.` and `-` separators such as `28.01.1960` are normalised to `/`)
  - email: valid format
  - glucose / haemoglobin / cholesterol: numeric and within plausible limits
  - duplicate detection: same email, or same name + date of birth
- Persistent storage in SQLite (`patients.db`, created automatically)
- Separate rejected-record history in SQLite, so invalid submissions remain visible for the demonstration
  without entering the valid patient table
- AI integration in `ai_service.py`; if Gemini is not configured, the app automatically provides a local
  screening estimate instead of showing an API-key warning. If a configured Gemini call fails, the
  record is still saved and its Remarks can be retried with **Retry AI**
- Editing only re-calls the AI when DOB or a blood value changes (not for an email-only edit)

## Project structure
```
app.py            Flask routes (REST API)
database.py       SQLite access
validators.py     Validation rules
ai_service.py     Gemini API call
templates/        index.html
static/           app.js, style.css
tests/            test_dataset.py (runs the 10 task-sheet records)
```

## Setup
```bash
python -m venv .venv
.venv\Scripts\activate          # Windows   (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env          # macOS/Linux: cp .env.example .env
# edit .env and paste your own key into GEMINI_API_KEY (free: https://aistudio.google.com/apikey)
python app.py
```
Open http://127.0.0.1:5000. `.env` is git-ignored, so no key is ever committed.
The model can be changed with `GEMINI_MODEL` in `.env`.

## REST API
| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/patients` | list records |
| POST | `/api/patients` | create (400 validation error, 409 duplicate) |
| PUT | `/api/patients/<id>` | update |
| DELETE | `/api/patients/<id>` | delete |
| POST | `/api/patients/<id>/remarks` | re-run the AI prediction |

## Task-sheet test data and expected result
| # | Name | Result | Reason |
|---|---|---|---|
| 1 | Robyn Pears | Saved | valid |
| 2 | John Hunter | Error | email `hunter@gmail` has no domain extension |
| 3 | Darryl Tim | Saved | valid |
| 4 | Peter Larry | Error | 31.11.2001 does not exist (November has 30 days) |
| 5 | Sam Kerr | Saved | valid |
| 6 | Robyn Pears | Error | duplicate of #1 (same email, name and DOB) |
| 7 | Madison XI | Saved | valid |
| 8 | Kris Wu | Error | DOB 19.10.2030 is in the future **and** email has no `@` |
| 9 | Tenille Singh | Saved | valid |
| 10 | Prem Kumar | Saved | valid |

Run the automated check (AI call stubbed): `python -m unittest tests.test_dataset -v`
