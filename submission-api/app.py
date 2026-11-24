"""Beta Epsilon server-side inquiry routing.
Public browser -> validated rate-limited Render API -> chapter-owned Google Apps Script.
Recruitment -> private Google Sheet; all other inquiries -> ASUAGRBE Gmail inbox.
Never put the Apps Script shared secret in browser JS or GitHub.
"""
import os
import re
from flask import Flask, jsonify, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.middleware.proxy_fix import ProxyFix
import requests

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
app.config["MAX_CONTENT_LENGTH"] = 16384
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["20 per hour"],
    storage_uri=os.getenv("RATELIMIT_STORAGE_URI", "memory://"),
)
ALLOWED_ORIGIN = os.getenv("ALLOWED_ORIGIN", "https://agr-beta-epsilon-design-test.onrender.com").rstrip("/")
RECRUITMENT = {"Interested in Joining", "Learn More About AGR"}
ADMIN = {"General Inquiry", "Alumni Relations", "Chapter History or Photos"}
ALL_PURPOSES = RECRUITMENT | ADMIN

def ready():
    return all([
        os.getenv("SUBMISSIONS_ENABLED") == "true",
        os.getenv("APPS_SCRIPT_WEBAPP_URL", "").startswith("https://script.google.com/macros/s/"),
        len(os.getenv("ROUTER_SHARED_SECRET", "")) >= 40,
    ])

@app.after_request
def response_headers(response):
    if request.headers.get("Origin") == ALLOWED_ORIGIN:
        response.headers["Access-Control-Allow-Origin"] = ALLOWED_ORIGIN
        response.headers["Vary"] = "Origin"
        response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response

@app.get("/health")
def health():
    return jsonify(status="ok", configured=ready())

@app.route("/api/submit", methods=["POST", "OPTIONS"])
@limiter.limit("5 per hour")
def submit():
    if request.method == "OPTIONS":
        return "", 204
    if request.headers.get("Origin") != ALLOWED_ORIGIN:
        return jsonify(error="Origin not allowed."), 403
    if not ready():
        return jsonify(error="This form is temporarily unavailable. Please try again later."), 503

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="Invalid request."), 400
    if data.get("website"):
        # Honeypot: do not notify spammers that this was blocked.
        return jsonify(status="received"), 202
    purpose = str(data.get("purpose", "")).strip()[:80]
    name = str(data.get("name", "")).strip()[:150]
    email = str(data.get("email", "")).strip().lower()[:254]
    message = str(data.get("message", "")).strip()[:4000]
    if (purpose not in ALL_PURPOSES or not 2 <= len(name) <= 150
        or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email)
        or not 5 <= len(message) <= 4000):
        return jsonify(error="Please complete all required fields correctly."), 400

    # Optional stronger bot protection; when configured, always validate.
    if os.getenv("TURNSTILE_SECRET_KEY"):
        try:
            verify = requests.post(
                "https://challenges.cloudflare.com/turnstile/v0/siteverify",
                data={
                    "secret": os.environ["TURNSTILE_SECRET_KEY"],
                    "response": str(data.get("turnstileToken", "")),
                    "remoteip": get_remote_address(),
                },
                timeout=10,
            )
            verify.raise_for_status()
            if verify.json().get("success") is not True:
                return jsonify(error="Security verification failed."), 400
        except requests.RequestException:
            app.logger.exception("Turnstile verification unavailable")
            return jsonify(error="Security verification unavailable."), 503

    try:
        upstream = requests.post(
            os.environ["APPS_SCRIPT_WEBAPP_URL"],
            json={
                "routerSecret": os.environ["ROUTER_SHARED_SECRET"],
                "purpose": purpose, "name": name, "email": email, "message": message
            },
            headers={"Content-Type": "application/json"},
            timeout=25,
            allow_redirects=True,
        )
        upstream.raise_for_status()
        result = upstream.json()
        expected = "saved" if purpose in RECRUITMENT else "emailed"
        if result.get("status") != expected:
            app.logger.error("Inquiry router did not confirm expected route")
            return jsonify(error="Your inquiry could not be delivered. Please try again."), 503
        return jsonify(status="submitted", route=result.get("route"), submissionId=result.get("submissionId")), 201
    except (requests.RequestException, ValueError):
        app.logger.exception("Chapter inquiry router unavailable")
        return jsonify(error="Your inquiry could not be delivered. Please try again."), 503

if __name__ == "__main__":
    app.run(port=int(os.getenv("PORT", "10000")))
