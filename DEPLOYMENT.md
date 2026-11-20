# Beta Epsilon — deployment and launch

The website source and a secure member-registration application live on the **beta-epsilon-website-staging** branch. This is **not a live deployment**. Never change Porkbun DNS until Render confirms the app is healthy.

## Requirements

- GitHub repository: J-Hagar/font.ag
- Render workspace owned by the site administrator
- Managed PostgreSQL database and backups
- SMTP sender with authenticated TLS and working delivery
- HTTPS custom domain: asu-agr-be.org
- Authorized administrator: Jim Hagar, hagaragrfinance@gmail.com
- Chapter-specific verified photos only; national AGR graphics only with appropriate use rights

## Render launch steps

1. Connect Render to GitHub and authorize repository access.
2. In Render, create **New > Blueprint**, selecting this repo and **beta-epsilon-website-staging**. The checked-in render.yaml describes the web service and managed database. **Review the paid resource selections before accepting any charges.** The public website and secure member portal both use the Python web service.
3. Configure SMTP_HOST, SMTP_USER, SMTP_PASSWORD, SMTP_FROM (use transactional email with SPF/DKIM). Render generates SECRET_KEY and DATABASE_URL through its blueprint.
4. Set PUBLIC_BASE_URL to the actual publicly reachable HTTPS hostname used for email verification links during staging. Change to https://asu-agr-be.org only after custom domain resolves with TLS.
5. Initialize tables from a Render shell: python -m flask --app app init-db. For subsequent releases use controlled schema migrations, not db.create_all().
6. Run all automated tests and manually verify applicant, pending, approved and admin login flows.
7. Register the first administrator through /register, answer the 1973 screening question and verify the administrator's email.
8. From a trusted Render shell run:
   python -m flask --app app promote-admin --email hagaragrfinance@gmail.com
   The administrator sets their own password at registration; nothing is seeded into source code.
9. Sign in and enroll administrator TOTP MFA; do not share the authenticator secret. Verify the full second-factor challenge during subsequent sign-in.
10. Add asu-agr-be.org and www.asu-agr-be.org to Render Custom Domains. Use **only the host-provided A/CNAME record values** in Porkbun. Preserve MX/TXT/SPF/DKIM and unrelated DNS records. Test HTTPS on both hostnames and set canonical redirect.
11. Test account approval, forgotten password, email delivery, unauthorized access, site uptime, database persistence and backup restoration. Then consider merging the staging branch after review.

## Membership rules

Both alumni and undergraduates use the same portal and access to approved general content. Every applicant must answer the chapter-year question (1973), verify their email and be independently approved by the administrator. The history question is a low-confidence filter, not identity proof.

## Operational and security considerations

- The code uses a Flask-Limiter in-memory rate limiter with gunicorn workers; production should use shared Redis rate-limit storage (or an equivalent perimeter rate limiter). Do not treat current limits as distributed enforcement.
- Configure observability, privacy policy, breach response, backup retention, SMTP deliverability, proper records consent, and routine dependency updates before inviting general membership.
- The public preview deliberately excludes chapter photos until authentic Beta Epsilon images are provided and approved.
- Never commit .env files, member records, administrator credentials, or passwords to GitHub.
- A static website by itself cannot safely serve membership documents. All private content must be served through authorization-checked routes or protected object storage.
- This repository does not presently include a member-directory or protected file-storage system; those must not be advertised as operational.
