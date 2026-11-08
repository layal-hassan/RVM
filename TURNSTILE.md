Cloudflare Turnstile protects public requests and applications before anything is
saved or emailed. Existing duplicate and rate limits remain active.

In Cloudflare → Turnstile → Add Widget:

1. Name: `RWM EL`.
2. Hostnames: `rwmel.se` and `www.rwmel.se`.
3. Mode: **Managed**. Pre-clearance is not needed.
4. Create the widget and copy its Site Key and Secret Key.

Add these values to the deployment environment or `.env` (either beside
`manage.py` or in its parent directory), then restart Django/Gunicorn:

```dotenv
TURNSTILE_ENABLED=true
TURNSTILE_SITE_KEY=your_public_site_key
TURNSTILE_SECRET_KEY=your_private_secret_key
```

The secret stays on the server. Do not commit it or put it in HTML/JavaScript.
Enabling protection with either key missing prevents startup. Without any keys,
protection remains disabled until configured; no demonstration keys are used.

Coverage: quick quote, contact, support, BRF inquiries, career applications,
feedback, outside-area requests, account signup, password reset, the service
request dialog, and the final steps of quote, consultation, electrician, service
and on-call booking. Earlier wizard steps do not require another challenge.
Staff/provider dashboard operations are unaffected.

The server calls Cloudflare Siteverify, checks success and hostname, and rejects
missing/invalid/expired/reused tokens and verification outages. Tokens are never
logged. AJAX forms retain entered data and refresh the challenge after a failed
submission. Ordinary forms offer a back button; wizard data remains in session.

For local browser testing, use Cloudflare's documented test key pair in a
development-only environment. Never deploy test keys to production:
https://developers.cloudflare.com/turnstile/troubleshooting/testing/

After deployment, test both a successful submission and a POST without
`cf-turnstile-response`; the latter must return HTTP 400 without creating a record
or sending an email. Ensure network/CSP rules permit `challenges.cloudflare.com`
for the browser script/frame and the server verification request.
