"""AGR Beta Epsilon website submissions: validated Render API -> chapter-owned Google Apps Script.
Public inquiries write to private Sheet1 only; member account requests write to a separate
private tab AND email ASUAGRBE@gmail.com. No direct browser access to Sheets or secrets.
"""
import os
import re
from uuid import uuid4
import requests
from flask import Flask, jsonify, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
app.config["MAX_CONTENT_LENGTH"] = 16384
limiter = Limiter(get_remote_address, app=app, default_limits=["25 per hour"],
                  storage_uri=os.getenv("RATELIMIT_STORAGE_URI", "memory://"))

ALLOWED_ORIGINS = {
    "https://agr-beta-epsilon-design-test.onrender.com",
    "https://agr-beta-epsilon.onrender.com",
    "https://asuagrbe.org",
    "https://www.asuagrbe.org",
}
PUBLIC_PURPOSES = {
    "Interested in Joining", "Learn More About AGR", "General Inquiry",
    "Alumni Relations", "Chapter History or Photos"
}
MEMBER_PURPOSE = "Member Account Request"

def ready():
    return (os.getenv("SUBMISSIONS_ENABLED") == "true"
            and os.getenv("APPS_SCRIPT_WEBAPP_URL", "").startswith("https://script.google.com/macros/s/")
            and len(os.getenv("ROUTER_SHARED_SECRET", "")) >= 40)

@app.after_request
def response_headers(response):
    origin = request.headers.get("Origin", "")
    if origin in ALLOWED_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
        response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response

@app.get("/health")
def health():
    return jsonify(status="ok", configured=ready(), router_deployment_suffix=(os.getenv("APPS_SCRIPT_WEBAPP_URL", "").split("/s/")[-1].split("/")[0][-8:] if "/s/" in os.getenv("APPS_SCRIPT_WEBAPP_URL", "") else "unavailable"))

@app.route("/api/submit", methods=["POST", "OPTIONS"])
@limiter.limit("5 per hour")
def submit():
    if request.method == "OPTIONS":
        return "", 204
    if request.headers.get("Origin") not in ALLOWED_ORIGINS:
        return jsonify(error="Origin not allowed."), 403
    if not ready():
        return jsonify(error="The submission service is not yet available. Your information has not been sent."), 503
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="Invalid request."), 400
    if data.get("website"):
        return jsonify(status="received"), 202

    purpose = str(data.get("purpose", "")).strip()[:80]
    name = str(data.get("name", "")).strip()[:150]
    email = str(data.get("email", "")).strip().lower()[:254]
    message = str(data.get("message", "")).strip()[:4000]
    address = str(data.get("address", "")).strip()[:400]
    phone = str(data.get("phone", "")).strip()[:40]
    stud_number = str(data.get("studNumber", "")).strip()[:64]
    affiliation = str(data.get("affiliation", "")).strip()[:40]

    if not (2 <= len(name) <= 150 and
            re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email)):
        return jsonify(error="Please enter your full name and a valid email."), 400
    if purpose == MEMBER_PURPOSE:
        if affiliation not in ("undergraduate", "alumni") or not 8 <= len(address) <= 400 or not re.fullmatch(r"[0-9+(). \-]{7,40}", phone) or not 1 <= len(stud_number) <= 64:
            return jsonify(error="Please select your membership status and enter your mailing address, phone number, and Stud Number (PIN)."), 400
    elif purpose in PUBLIC_PURPOSES:
        if not 5 <= len(message) <= 4000:
            return jsonify(error="Please provide your question or message."), 400
    else:
        return jsonify(error="Please select a valid inquiry category."), 400

    if os.getenv("TURNSTILE_SECRET_KEY"):
        try:
            verify = requests.post(
                "https://challenges.cloudflare.com/turnstile/v0/siteverify",
                data={"secret": os.environ["TURNSTILE_SECRET_KEY"],
                      "response": str(data.get("turnstileToken", "")),
                      "remoteip": get_remote_address()}, timeout=10)
            verify.raise_for_status()
            if verify.json().get("success") is not True:
                return jsonify(error="Security verification failed."), 400
        except requests.RequestException:
            app.logger.exception("Security verification unavailable")
            return jsonify(error="Security verification temporarily unavailable."), 503

    submission_id = str(uuid4())
    try:
        response = requests.post(
            os.environ["APPS_SCRIPT_WEBAPP_URL"],
            json={"routerSecret": os.environ["ROUTER_SHARED_SECRET"],
                  "submissionId": submission_id, "purpose": purpose, "name": name,
                  "email": email, "message": message,
                  "address": address if purpose == MEMBER_PURPOSE else "",
                  "phone": phone if purpose == MEMBER_PURPOSE else "",
                  "studNumber": stud_number if purpose == MEMBER_PURPOSE else "",
                  "affiliation": affiliation if purpose == MEMBER_PURPOSE else ""},
            timeout=28,
            allow_redirects=True,
        )
        response.raise_for_status()
        app.logger.warning('Google router HTTP response: status=%s content_type=%s host=%s redirects=%s', response.status_code, response.headers.get('Content-Type','unknown').split(';')[0], requests.utils.urlparse(response.url).hostname, len(response.history))
        result = response.json()
        route = "member-sheet-and-email" if purpose == MEMBER_PURPOSE else "public-sheet-only"
        if result.get("status") != "submitted" or result.get("route") != route:
            app.logger.error("Chapter router rejected %s: http=%s fields=%s status=%r returned_route=%r failure_category=%r", route, response.status_code, sorted(result.keys()) if isinstance(result, dict) else [], result.get("status") if isinstance(result, dict) else None, result.get("route") if isinstance(result, dict) else None, (result.get("message") or result.get("error")) if isinstance(result, dict) and (result.get("message") or result.get("error")) in {"Auth","Name/email","Member fields","Public fields","Public ads","Tab","Save"} else "other")
            return jsonify(error="The inquiry was not confirmed. Please contact the chapter office."), 503
        return jsonify(status="submitted", route=route, submissionId=result.get("submissionId")), 201
    except (requests.RequestException, ValueError):
        app.logger.exception("Unable to reach chapter inbox or private Sheet")
        return jsonify(error="The inquiry could not be confirmed. Please try again."), 503

if __name__ == "__main__":
    app.run(port=int(os.getenv("PORT", "10000")))
