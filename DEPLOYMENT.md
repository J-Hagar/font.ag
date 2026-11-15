# Secure deployment checklist — Beta Epsilon

## Current status
This repository is **not deployed**. The Porkbun domain must remain unchanged until a running, tested hosting service provides exact DNS values. Do not accept any placeholder login as real authentication.

## Approved identity model
- All alumni and undergraduate brothers share one portal and equal general-member access.
- Registration asks the Arkansas State Beta Epsilon charter year (1973).
- Correct response is **not** proof of identity; email verification and independent administrator approval are mandatory.
- First administrator: Jim Hagar, hagaragrfinance@gmail.com. Administrator must set password privately.
- Administrator MFA is a prerequisite for production go-live.

## Infrastructure plan
1. Link this GitHub repository to Render under an account owned by the chapter administrator.
2. Use a persistent managed PostgreSQL database with backups; no SQLite on an ephemeral disk.
3. Configure HTTPS, TLS hostname, secrets in Render's environment, and a transactional email sender.
4. Configure an initial administrator invitation flow requiring email ownership and MFA. Never seed a password in a file or chat.
5. Run automated tests for unauthenticated access, pending approvals, password resets, CSRF, rate limiting, and admin access.
6. Configure custom domain in Render. Copy only the exact host-provided A/CNAME records into Porkbun; preserve existing MX, SPF, DKIM, and other unrelated records.
7. Verify both www and apex HTTPS redirect behavior, email verification links, protected resources, database persistence after restart, backups and restores, and admin MFA before launch.

## Security restrictions
- Never serve private member photos, files, member directories, or database contents from a public static directory.
- No credentials, personal records, or tokens in GitHub.
- Obtain consent prior to listing member contact details.
- Only use verified Beta Epsilon chapter photos and licensed AGR artwork.
