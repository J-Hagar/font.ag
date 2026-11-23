"""Beta Epsilon website submissions -> private Google Sheet.

Deploy only with Google service-account credentials configured as a Render secret,
and after granting that service account editor access to the specified Sheet.
Never expose credentials or a public Sheets API key in browser JavaScript.
"""
import json
import os
import re
import secrets
from datetime import datetime, timezone
from uuid import uuid4

from flask import Flask, request, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
app.config["MAX_CONTENT_LENGTH"] = 16_384
limiter = Limiter(get_remote_address, app=app, default_limits=["100 per hour"], storage_uri=os.getenv("RATELIMIT_STORAGE_URI", "memory://"))

SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "1smGK3171vIcxUT93Qn9PestvwjZeupwH083qFI_NlUs")
SHEET_RANGE = "'Sheet1'!A:I"
ALLOWED_ORIGIN = os.getenv("ALLOWED_ORIGIN", "https://agr-beta-epsilon-design-test.onrender.com").rstrip("/")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
VALID_PURPOSES = {"Interested in Joining", "Learn More About AGR", "Alumni Relations", "Chapter History or Photos", "General Inquiry"}

def ready():
    return bool(os.getenv("SUBMISSIONS_ENABLED") == "true" and os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON") and os.getenv("TURNSTILE_SECRET_KEY") and os.getenv("RATELIMIT_STORAGE_URI"))

def cors(response):
    origin = request.headers.get("Origin", "")
    if origin == ALLOWED_ORIGIN:
        response.headers["Access-Control-Allow-Origin"] = ALLOWED_ORIGIN
        response.headers["Vary"] = "Origin"
        response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response

app.after_request(cors)

@app.get("/health")
def health():
    return jsonify(status="ok", configured=ready())

@app.route("/api/submit", methods=["POST", "OPTIONS"])
@limiter.limit("5 per hour")
def submit():
    if request.method == "OPTIONS":
        return "", 204
    if not ready():
        return jsonify(error="Submissions are not yet configured."), 503
    if request.headers.get("Origin") != ALLOWED_ORIGIN:
        return jsonify(error="Origin not allowed."), 403
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="Invalid request."), 400
    # Honeypot: legitimate user leaves blank.
    if data.get("website"):
        return jsonify(status="received"), 202
    purpose = str(data.get("purpose", ""))[:80]
    full_name = str(data.get("name", "")).strip()[:150]
    email = str(data.get("email", "")).strip().lower()[:254]
    message = str(data.get("message", "")).strip()[:4000]
    turnstile = str(data.get("turnstileToken", ""))
    if purpose not in VALID_PURPOSES or not 2 <= len(full_name) <= 150 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email) or not 5 <= len(message) <= 4000 or not turnstile:
        return jsonify(error="Please complete the required fields."), 400
    import requests
    try:
        verify = requests.post(
            "https://challenges.cloudflare.com/turnstile/v0/siteverify",
            data={"secret":os.environ["TURNSTILE_SECRET_KEY"], "response":turnstile, "remoteip":get_remote_address()},
            timeout=10,
        )
        verify.raise_for_status()
        if verify.json().get("success") is not True:
            return jsonify(error="Security verification failed."), 400
        creds = service_account.Credentials.from_service_account_info(
            json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]), scopes=SCOPES
        )
        client = AuthorizedSession(creds)
        submitted_at = datetime.now(timezone.utc).isoformat()
        submission_id = str(uuid4())
        # Prefix potentially formula-like input to prevent Google Sheets formula injection.
        def safe(value):
            return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value
        row = [submitted_at, submission_id, purpose, safe(full_name), safe(email), safe(message), ALLOWED_ORIGIN, "New", ""]
        endpoint = "https://sheets.googleapis.com/v4/spreadsheets/" + SHEET_ID + "/values/" + "'Sheet1'!A:I" + ":append"
        result = client.post(endpoint, params={"valueInputOption":"RAW", "insertDataOption":"INSERT_ROWS"}, json={"values":[row]}, timeout=15)
        result.raise_for_status()
        return jsonify(status="saved", submissionId=submission_id), 201
    except Exception:
        app.logger.exception("Unable to save website submission")
        return jsonify(error="We could not save your inquiry. Please contact the chapter office once its official mailbox is active."), 503

if __name__ == "__main__":
    app.run(port=int(os.getenv("PORT", "10000")))
