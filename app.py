import os
import hmac
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from functools import wraps
from urllib.parse import urlparse

import click
import pyotp
from flask import Flask, abort, flash, redirect, render_template_string, request, session, url_for
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from sqlalchemy import func
from werkzeug.security import check_password_hash, generate_password_hash
from markupsafe import escape

app = Flask(__name__, static_folder=".", static_url_path="/assets")
app.config.update(
    SECRET_KEY=os.getenv("SECRET_KEY", ""),
    SQLALCHEMY_DATABASE_URI=os.getenv("DATABASE_URL", "").replace("postgres://", "postgresql://", 1),
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    SESSION_COOKIE_SECURE=os.getenv("APP_ENV") != "local",
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    REMEMBER_COOKIE_SECURE=True,
    MAX_CONTENT_LENGTH=1024 * 64,
)
if not app.config["SECRET_KEY"] or len(app.config["SECRET_KEY"]) < 32:
    raise RuntimeError("SECRET_KEY must be at least 32 characters.")
if not app.config["SQLALCHEMY_DATABASE_URI"]:
    raise RuntimeError("DATABASE_URL must be configured.")
db = SQLAlchemy(app)
csrf = CSRFProtect(app)
limiter = Limiter(get_remote_address, app=app, default_limits=["120 per hour"], storage_uri="memory://")
login_manager = LoginManager(app)
login_manager.login_view = "login"
serializer = URLSafeTimedSerializer(app.config["SECRET_KEY"])

class Member(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(254), unique=True, index=True, nullable=False)
    password_hash = db.Column(db.String(512), nullable=False)
    member_type = db.Column(db.String(20), nullable=False)
    email_verified = db.Column(db.Boolean, default=False, nullable=False)
    approved = db.Column(db.Boolean, default=False, nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    totp_secret = db.Column(db.String(64), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    @property
    def is_active(self):
        return True

@login_manager.user_loader
def load_user(uid):
    return db.session.get(Member, int(uid)) if uid.isdigit() else None

@app.after_request
def security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; "
        "img-src 'self' data:; frame-ancestors 'none'; form-action 'self'; base-uri 'self'"
    )
    if request.is_secure:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Cache-Control"] = "no-store" if request.path.startswith(("/portal", "/admin", "/login", "/register", "/mfa")) else "public, max-age=300"
    return response

def mail(to, subject, content):
    required = ["SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM"]
    if not all(os.getenv(k) for k in required):
        raise RuntimeError("Outbound SMTP is not configured.")
    msg = EmailMessage()
    msg["From"] = os.environ["SMTP_FROM"]
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(content)
    with smtplib.SMTP(os.environ["SMTP_HOST"], int(os.getenv("SMTP_PORT", "587")), timeout=15) as server:
        server.starttls()
        server.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
        server.send_message(msg)

def baseurl():
    return os.environ.get("PUBLIC_BASE_URL", "https://asu-agr-be.org").rstrip("/")

def page(title, body):
    return render_template_string("""<!doctype html><html lang="en"><head><meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <title>{{ title }} | AGR Beta Epsilon</title><link rel="stylesheet" href="/assets/styles.css"></head>
      <body><header><a class="brand" href="/"><span class="mark">ΑΓΡ</span>
      <span>ALPHA GAMMA RHO<small>BETA EPSILON · ARKANSAS STATE</small></span></a>
      <nav><a href="/">Home</a><a href="/portal">Member Portal</a>
      {% if current_user.is_authenticated %}<a href="/logout">Sign out</a>{% else %}
      <a href="/login">Sign in</a><a href="/register">Register</a>{% endif %}</nav></header>
      <main><section><h1>{{ title }}</h1>
      {% with messages=get_flashed_messages() %}{% if messages %}
      <div role="status">{% for item in messages %}<p>{{ item }}</p>{% endfor %}</div>
      {% endif %}{% endwith %}
      """ + body + """</section></main><footer>Alpha Gamma Rho · Beta Epsilon · Arkansas State University</footer>
      </body></html>""", title=title)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/")
def home():
    return app.send_static_file("index.html")

@app.route("/register", methods=["GET", "POST"])
@limiter.limit("8 per hour")
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()[:150]
        email = request.form.get("email", "").strip().lower()[:254]
        password = request.form.get("password", "")
        member_type = request.form.get("member_type", "")
        year = request.form.get("year", "").strip()
        valid = all([name, "@" in email, len(password) >= 12,
                     member_type in ("alumni", "undergraduate"),
                     hmac.compare_digest(year, "1973")])
        if not valid:
            flash("Review all fields, including the chapter-history answer and a password of at least 12 characters.")
        elif db.session.query(Member).filter_by(email=email).first():
            flash("If this email is eligible, use the sign-in or recovery process.")
        else:
            member = Member(name=name, email=email, password_hash=generate_password_hash(password),
                            member_type=member_type)
            db.session.add(member)
            db.session.commit()
            link = baseurl() + url_for("verify_email", token=serializer.dumps(email, salt="email-verify"))
            try:
                mail(email, "Verify your Beta Epsilon member email",
                     "Verify your email:\n" + link + "\nThis link expires in 24 hours.")
            except Exception:
                app.logger.exception("Could not deliver verification email")
                flash("Registration saved, but verification email could not be sent. Contact the administrator.")
                return redirect(url_for("login"))
            flash("Check your email to verify your address. Administrator approval is also required.")
            return redirect(url_for("login"))
    return page("Register", """<p>For Beta Epsilon alumni and undergraduate brothers. Approval is required.</p>
      <form method="post"><input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
      <label>Full name<input name="name" required maxlength="150"></label>
      <label>Email<input type="email" name="email" required></label>
      <label>Member status<select name="member_type" required><option value="alumni">Alumnus</option>
      <option value="undergraduate">Undergraduate</option></select></label>
      <label>In what year was Beta Epsilon chartered at Arkansas State?
      <input name="year" inputmode="numeric" required></label>
      <label>Choose a password (12 characters minimum)<input type="password" name="password" minlength="12" required autocomplete="new-password"></label>
      <button type="submit">Request membership</button></form>""")

@app.get("/verify/<token>")
@limiter.limit("20 per hour")
def verify_email(token):
    try:
        email = serializer.loads(token, salt="email-verify", max_age=86400)
    except (BadSignature, SignatureExpired):
        abort(400, "Verification link is invalid or expired.")
    member = db.session.query(Member).filter_by(email=email).first()
    if member:
        member.email_verified = True
        db.session.commit()
    flash("Email verified. Membership access still requires administrator approval.")
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        member = db.session.query(Member).filter_by(email=email).first()
        pw = request.form.get("password", "")
        if not member or not check_password_hash(member.password_hash, pw):
            flash("Invalid credentials.")
        elif not member.email_verified or not member.approved:
            flash("Your account is not yet verified and approved.")
        else:
            session.clear()
            if member.is_admin and member.totp_secret:
                session["mfa_pending_user"] = member.id
                return redirect(url_for("mfa"))
            login_user(member, remember=False, fresh=True)
            if member.is_admin:
                return redirect(url_for("setup_mfa"))
            return redirect(url_for("portal"))
    return page("Member sign in", """<form method="post">
      <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
      <label>Email<input type="email" name="email" required autocomplete="email"></label>
      <label>Password<input name="password" type="password" required autocomplete="current-password"></label>
      <button type="submit">Sign in</button></form>
      <p><a href="/register">Request an account</a> · <a href="/recover">Forgot password?</a></p>""")

@app.route("/mfa", methods=["GET", "POST"])
@limiter.limit("8 per minute")
def mfa():
    uid = session.get("mfa_pending_user")
    member = db.session.get(Member, uid) if uid else None
    if not member or not member.is_admin or not member.totp_secret:
        abort(403)
    if request.method == "POST":
        if pyotp.TOTP(member.totp_secret).verify(request.form.get("code", ""), valid_window=1):
            session.clear()
            login_user(member, fresh=True)
            return redirect(url_for("portal"))
        flash("Invalid authenticator code.")
    return page("Administrator verification", """<form method="post">
      <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
      <label>Six-digit authenticator code<input name="code" required inputmode="numeric" autocomplete="one-time-code"></label>
      <button type="submit">Verify</button></form>""")

def approved_only(fn):
    @wraps(fn)
    @login_required
    def inner(*args, **kwargs):
        if not current_user.approved or not current_user.email_verified:
            abort(403)
        if current_user.is_admin and not current_user.totp_secret and request.endpoint != "setup_mfa":
            return redirect(url_for("setup_mfa"))
        return fn(*args, **kwargs)
    return inner

def admin_only(fn):
    @wraps(fn)
    @approved_only
    def inner(*args, **kwargs):
        if not current_user.is_admin or not current_user.totp_secret:
            abort(403)
        return fn(*args, **kwargs)
    return inner

@app.route("/admin/mfa/setup", methods=["GET", "POST"])
@login_required
def setup_mfa():
    if not current_user.is_admin or not current_user.approved or not current_user.email_verified:
        abort(403)
    if current_user.totp_secret:
        return redirect(url_for("admin"))
    secret = session.get("enrollment_secret")
    if not secret:
        secret = pyotp.random_base32()
        session["enrollment_secret"] = secret
    if request.method == "POST":
        if pyotp.TOTP(secret).verify(request.form.get("code", ""), valid_window=1):
            current_user.totp_secret = secret
            db.session.commit()
            session.pop("enrollment_secret", None)
            return redirect(url_for("admin"))
        flash("Incorrect code; check the authenticator app.")
    return render_template_string("""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Set up admin MFA</title></head><body>
      <main><h1>Set up administrator MFA</h1><p>Add this secret to a TOTP authenticator app, then enter a six-digit code.
      Treat the secret as confidential.</p><code>{{ secret }}</code>
      <p>Authenticator URL: <code>{{ uri }}</code></p>
      <form method="post"><input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
      <label>Verification code<input name="code" required></label><button>Enable MFA</button></form></main></body></html>""",
      secret=secret, uri=pyotp.TOTP(secret).provisioning_uri(name=current_user.email, issuer_name="AGR Beta Epsilon"))

@app.get("/portal")
@approved_only
def portal():
    return page("Beta Epsilon Member Portal", """<p>Welcome to the unified alumni and undergraduate portal.
      Member directories, private archives, and chapter documents will only be added after verified permissions and content approvals.</p>
      {% if current_user.is_admin %}<p><a href="/admin">Administrator dashboard</a></p>{% endif %}""")

@app.route("/admin", methods=["GET", "POST"])
@admin_only
def admin():
    if request.method == "POST":
        member_id = request.form.get("member_id", "", type=int)
        member = db.session.get(Member, member_id)
        action = request.form.get("action")
        if member and not member.is_admin and action in ("approve", "reject"):
            if action == "approve" and member.email_verified:
                member.approved = True
                db.session.commit()
                flash("Member approved.")
            elif action == "reject":
                db.session.delete(member)
                db.session.commit()
                flash("Application rejected.")
    pending = db.session.query(Member).filter_by(approved=False).order_by(Member.created_at).all()
    rows = []
    for member in pending:
        if member.is_admin:
            continue
        rows.append({"id": member.id, "name": member.name, "email": member.email,
                     "type": member.member_type, "verified": member.email_verified})
    return render_template_string("""<!doctype html><html lang="en"><head><meta charset="utf-8">
      <title>Beta Epsilon administrator</title><link rel="stylesheet" href="/assets/styles.css"></head><body>
      <main><section><h1>Membership approval</h1><p><a href="/portal">Return to portal</a></p>
      <p>Independently confirm each applicant's Beta Epsilon membership before approval.</p>
      {% for m in members %}<article><strong>{{ m.name }}</strong> — {{ m.email }}
      ({{ m.type }}; email verified: {{ m.verified }})
      <form method="post"><input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
      <input type="hidden" name="member_id" value="{{ m.id }}">
      <button name="action" value="approve" {% if not m.verified %}disabled{% endif %}>Approve</button>
      <button name="action" value="reject">Reject</button></form></article>
      {% else %}<p>No pending applications.</p>{% endfor %}</section></main></body></html>""", members=rows)

@app.route("/recover", methods=["GET", "POST"])
@limiter.limit("5 per hour")
def recover():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        member = db.session.query(Member).filter_by(email=email).first()
        if member:
            token = serializer.dumps([email, member.password_hash[-16:]], salt="reset")
            try:
                mail(email, "Beta Epsilon password reset", baseurl() + url_for("reset_password", token=token) +
                     "\nThis link expires in 30 minutes.")
            except Exception:
                app.logger.exception("Password reset email failed")
        flash("If an account exists, a reset email has been requested.")
    return page("Reset password", """<form method="post"><input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
    <label>Account email<input type="email" name="email" required></label><button>Request reset link</button></form>""")

@app.route("/reset/<token>", methods=["GET", "POST"])
@limiter.limit("8 per hour")
def reset_password(token):
    try:
        data = serializer.loads(token, salt="reset", max_age=1800)
    except (BadSignature, SignatureExpired):
        abort(400, "Reset link is invalid or expired.")
    member = db.session.query(Member).filter_by(email=data[0]).first()
    if not member or not hmac.compare_digest(member.password_hash[-16:], data[1]):
        abort(400)
    if request.method == "POST":
        password = request.form.get("password", "")
        if len(password) < 12:
            flash("Use at least 12 characters.")
        else:
            member.password_hash = generate_password_hash(password)
            db.session.commit()
            flash("Password changed. Sign in with the new password.")
            return redirect(url_for("login"))
    return page("Choose new password", """<form method="post">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
    <label>New password (12+ characters)<input name="password" type="password" minlength="12" required></label>
    <button>Update password</button></form>""")

@app.get("/logout")
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect(url_for("home"))

@app.cli.command("init-db")
def init_db():
    """Create database tables after the managed database is provisioned."""
    db.create_all()
    click.echo("Database initialized.")

@app.cli.command("promote-admin")
@click.option("--email", required=True)
def promote_admin(email):
    """Promote a previously registered, email-verified first administrator."""
    configured = os.getenv("ADMIN_EMAIL", "").strip().lower()
    if not configured or email.strip().lower() != configured:
        raise click.ClickException("Email must match configured ADMIN_EMAIL.")
    member = db.session.query(Member).filter_by(email=configured).first()
    if not member or not member.email_verified:
        raise click.ClickException("Admin must register and verify email first.")
    member.approved = True
    member.is_admin = True
    db.session.commit()
    click.echo("Administrator promoted. MFA enrollment is mandatory at next login.")

if __name__ == "__main__":
    app.run(debug=False)
