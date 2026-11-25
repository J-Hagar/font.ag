# Beta Epsilon Website — Private Google Sheets Submission API

**Status: code prepared, not deployed.** Do not enable browser submission until the live API reports configured=true and a test row is verified in the private Sheet.

Destination: [AGR-BE Submission Form Entries](https://docs.google.com/spreadsheets/d/1smGK3171vIcxUT93Qn9PestvwjZeupwH083qFI_NlUs/edit), tab Sheet1, columns A:I.

## Security prerequisites

1. Create a Google Cloud service account dedicated to the chapter form. Enable the Google Sheets API on its project.
2. Give **Editor** access to the Google Sheet **only** to that service account email. Do not share publicly.
3. In the Render service environment (not GitHub), add `GOOGLE_SERVICE_ACCOUNT_JSON` containing the service account credential JSON. Never commit credentials.
4. Configure `TURNSTILE_SECRET_KEY` on the server and its matching Turnstile site key in the website contact form.
5. Configure a shared rate-limit store via `RATELIMIT_STORAGE_URI` (e.g. Redis with TLS), because worker-local rate limiting is insufficient.
6. Set `ALLOWED_ORIGIN=https://agr-beta-epsilon-design-test.onrender.com` and `GOOGLE_SHEET_ID` to the verified Sheet ID.
7. Deploy as a **separate Render Python web service** with root directory `submission-api`, build `pip install -r requirements.txt` and start `gunicorn --bind 0.0.0.0:$PORT --workers 2 app:app`.
8. In the public site, configure the HTTPS API endpoint and Turnstile site key. Remove the existing manual copy-to-Facebook fallback only after end-to-end submission testing.
9. Test with a harmless dummy inquiry and verify that one row is appended, values align with the headers, duplicate or invalid requests are rejected, and errors return without exposing secrets.

Security considerations: add abuse monitoring, opt-in privacy notice, retention/deletion schedule, and error notifications. The sheet should remain private. No member-only authentication data belongs in this public contact sheet.

The current backend intentionally refuses writes if any required credential or abuse control is missing.
