import os
os.environ.setdefault("SECRET_KEY", "test-secret-key-longer-than-thirty-two-characters")
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["APP_ENV"] = "local"
os.environ["WTF_CSRF_ENABLED"] = "false"

import unittest
from unittest.mock import patch

from app import app, db, Member

class MemberWorkflowTest(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        self.ctx = app.app_context()
        self.ctx.push()
        db.create_all()
        self.client = app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def registration(self, year="1973"):
        return self.client.post("/register", data={
            "name": "Chapter Test Member", "email": "member@example.org",
            "member_type": "alumni", "year": year,
            "password": "a-good-test-password-2026",
        }, follow_redirects=True)

    @patch("app.mail")
    def test_registration_requires_correct_history(self, mail):
        self.registration("1972")
        self.assertEqual(db.session.query(Member).count(), 0)
        self.registration("1973")
        self.assertEqual(db.session.query(Member).count(), 1)
        self.assertFalse(db.session.query(Member).first().approved)
        self.assertFalse(db.session.query(Member).first().email_verified)

    @patch("app.mail")
    def test_pending_member_cannot_enter_portal(self, mail):
        self.registration()
        response = self.client.post("/login", data={
            "email": "member@example.org", "password": "a-good-test-password-2026",
        }, follow_redirects=True)
        self.assertIn(b"not yet verified and approved", response.data)
        response = self.client.get("/portal")
        self.assertEqual(response.status_code, 302)

    def test_health(self):
        self.assertEqual(self.client.get("/health").json, {"status": "ok"})

if __name__ == "__main__":
    unittest.main()
