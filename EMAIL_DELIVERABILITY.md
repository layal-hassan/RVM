# Email delivery investigation

## Production deployment: use the service's PostgreSQL settings

The VPS service `rwmel` configures `USE_POSTGRES=true`, `DB_NAME=rwmel`,
`DB_HOST=localhost`, and `DB_PORT=5432` in its systemd Environment. The login
shell selects SQLite instead. The SQLite snapshot is not a backup of the live
PostgreSQL database. Do not replace or migrate that SQLite file as part of this
production update.

`python service_manage.py <command>` reads the service environment in memory,
checks that its working directory matches this checkout, and invokes Django
with the same PostgreSQL settings. It never prints passwords or puts them on
the command line. It refuses unresolved EnvironmentFiles and missing database
configuration rather than falling back to SQLite.

After publishing the new deployment helpers, run in `/var/www/rwmel` with the
virtualenv active:

```bash
git pull --ff-only origin main &&
python service_manage.py backup_database &&
python service_manage.py makemigrations --merge --noinput &&
python service_manage.py apply_spam_protection &&
python service_manage.py check &&
python service_manage.py check_email_config &&
python service_manage.py collectstatic --noinput &&
sudo systemctl restart rwmel &&
sudo systemctl is-active rwmel
```

The backup command creates a private custom-format pg_dump archive in
`/var/backups`. A failure stops the chain. The VPS has a separate migration
`0058_merge_20261027_1333` absent from the local checkout, so merge generation
must occur against the VPS's actual migration graph. Keep the generated merge
file for later inclusion in the repository; do not remove migration history.

`apply_spam_protection` targets `0058_publicformsubmissionbucket` explicitly,
not the graph's latest merge. The independent table depends on baseline 0054,
so pending pricing/workflow/template changes on the other branch are not
included. `0059_merge_spam_protection` joins the repository branches without
operations; a VPS with additional local merges needs merge generation again.
The command inspects the targeted PostgreSQL migration plan and permits only
the known table creation and empty ancestor migrations in this app. Any other
required schema/data change or rollback stops it before migration execution.
An already-applied table returns without rolling back descendants. This lets
the protection table deploy while preserving unrelated pending work. If it stops,
inspect `python service_manage.py migrate --plan` rather than using --fake or
deleting migration records. `pg_dump` must be installed and compatible with
the server version. The archive must be retained separately from the checkout.

## Repeated submission protection

`PublicFormSpamProtectionMiddleware` now guards public contact, support, BRF,
careers, feedback, outside-area requests, quick quotes, quote submission,
signup/password reset, and final consultation/electrician/service/on-call
booking steps. GET requests, intermediate booking steps, dashboard and provider
actions are unaffected.

Limits are shared across forms and application workers in the database:

- Same source IP: 5 attempts per 10-minute window, 20 per UTC day.
- Same email or phone: 3 attempts per hourly window, 5 per UTC day.
- Identical meaningful form content: one attempt per 10 minutes.

Rejected requests return HTTP 429, `Retry-After`, and `Cache-Control: no-store`,
before the view saves records or sends email. Failed validation and duplicate
attempts may consume quota. New CSRF masks, fresh quote tokens and unknown
extra fields do not change the duplicate fingerprint. Swedish local and
international phone formats are normalized, as are Gmail dots/plus aliases.
The token check in the quick-quote view still prevents token reuse. Expired
limits are removed on subsequent submissions; IP/email/phone keys are HMAC
hashes, not plaintext. Fixed windows can allow a boundary burst, but daily
limits still prevent fifty submissions with one identity or source per day.

Deploy the middleware, protection helper, active settings and updated earlier
quote files together, then restart Django. Migration 0058 from the prior repair
must have been applied (`python manage.py migrate`). If production uses a
separate settings module, include
`electricity.middleware.PublicFormSpamProtectionMiddleware` after session,
CSRF and authentication middleware there too.

### Proxy configuration

Direct connections use `REMOTE_ADDR`. Behind a reverse proxy, explicitly set
`FORM_TRUSTED_PROXY_NETWORKS` to the actual proxy IPs/CIDRs in production. For
example, **only if Nginx connects locally over IPv4 loopback**:

```text
FORM_TRUSTED_PROXY_NETWORKS=127.0.0.1/32
```

Nginx must forward the client chain using
`proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;`. The application
walks the chain from the trusted peer toward the client and uses the nearest
untrusted address. Do not list public client networks or use `0.0.0.0/0` or
`::/0`. With no trusted proxy configured, forwarded headers are ignored and
clients behind the proxy share its quota. Verify the actual deployment before
enabling this setting. Public shared connections can also share the IP quota.

Test: sending the same support request fifty times produces one ticket/email
and 49 HTTP 429 responses. Other tests cover shared limits across routes,
changing IPs/emails, normalized phones, Gmail aliases, daily expiry, forwarded
header spoofing, trusted proxy chains and final booking session identities.
These are rate and repetition controls; distributed bots using fresh identities
and addresses still require additional provider/WAF or CAPTCHA controls.

## Confirmed form abuse in the supplied bounce

The supplied 2026-10-29 bounce embeds an original quick-quote confirmation
whose customer name contains advertising text and a shortened URL. The
application interpolated that untrusted name into an email to the submitted
recipient. This confirms an abuse path; it does not prove that all legitimate
mail has a reputation or authentication problem.

Gmail rejected that recipient at `RCPT TO` with `550 5.1.1` (no such mailbox).
The outer bounce has `X-Spam: Yes`; its DKIM/DMARC passes authenticate
`mailchannels.net`, not the embedded message from `rwmel.se`. The embedded
message was submitted using the support account and contains a Hostinger DKIM
signature for `rwmel.se`, but no recipient-side verification result is supplied.
`X-MC-Relay: Bad` is present in the original; its precise meaning requires
MailChannels/Hostinger interpretation rather than an assumed blacklist verdict.

The quick-quote path now rejects links/markup in the name, includes a honeypot
and an expiring signed form token, and enforces one-use tokens plus the shared
database limits described above. Expired buckets are cleaned on submission.
Failed/replayed attempts can consume the current window's quota.
External confirmations contain fixed text and a server-generated reference,
without visitor-supplied names, phone numbers, links, or message text. Internal
notifications retain submitted information for staff review.

Before restarting the application after deploying these changes, run:

```powershell
python manage.py migrate
python manage.py check_email_config
```

Deploy models, migration, forms, view, protection helper, and landing template
together. Purge any cached homepage HTML so visitors receive a fresh token;
forms left open over two hours need a page reload. The database table is
required. Configure trusted proxy networks as described above so the IP quota
does not apply to the proxy's combined traffic. Untrusted forwarded headers
are deliberately ignored. These controls reduce automated abuse;
a distributed bot can still fetch fresh forms. A server-verified CAPTCHA/WAF
challenge needs deployment-specific configuration if that abuse continues.

Do not retry the nonexistent recipient or visit the advertising URL. After
deployment, inspect a legitimate company's received notification headers and
Hostinger delivery logs. Reputation recovery and the original spam verdict
still need provider-side evidence; neither is proven resolved by these changes.

Checked on 2026-10-29. Public DNS for `rwmel.se` returned:

- MX: `mx1.hostinger.com` and `mx2.hostinger.com`.
- SPF: `v=spf1 include:_spf.mail.hostinger.com ~all`.
- DMARC: `v=DMARC1; p=none`.
- DKIM: `hostingermail-a`, `hostingermail-b`, and `hostingermail-c` CNAMEs point
  to their corresponding `*.dkim.mail.hostinger.com` records.

These records match Hostinger's documented mail setup. DNS presence alone does
not prove a particular email passes authentication or explain its spam verdict.
Changing DMARC to `quarantine` or `reject` does not repair delivery or signing.

## Application repair

Active settings now load the support and invoice credential pairs, sender
addresses, and booking destinations from the environment. Previously the
support credentials were ignored. Connection selection now recognizes SMTP
subclasses, including `electricity.email_backend.EmailBackend`; previously its
name failed a substring check and silently selected Django's default account.
Incomplete SMTP credential pairs now fail explicitly.

Deploy the changed Python files and restart the Django application. From the
same environment and settings used by the deployed application, run:

```powershell
python manage.py check_email_config
```

This command neither sends mail nor prints passwords. Support, bookings, and
contact notifications should use the support account, and invoices should use
the invoice account. Every From address must be the authenticated mailbox or
an alias explicitly authorized by the provider. The default SMTP account also
needs permission for DEFAULT_FROM_EMAIL and SERVER_EMAIL because Django system
mail (including password resets) uses it. If these are support addresses, use
the support credential pair for EMAIL_HOST_USER/EMAIL_HOST_PASSWORD, retaining
the explicit INVOICE_EMAIL_HOST_* pair for invoices.

## Evidence needed to finish diagnosis

After deployment, use a genuine website submission and inspect the received
message's full source in the affected company mailbox. Preserve:

- `Authentication-Results`: SPF, DKIM, DMARC results and their domains.
- `DKIM-Signature`: particularly `d=` and `s=` (the actual signing selector).
- `Return-Path`, `From`, `Message-ID`, and `Received`.
- `X-Spam-*` / `X-Spamd-*` / provider-specific filtering headers, if present.

Redact customer data and message content before sharing. A DKIM selector seen
in the message must resolve in DNS, even if the three standard selectors exist.
DMARC needs a passing, aligned SPF or DKIM result. If authentication passes,
use the spam verdict, timestamp, Message-ID, and outbound IP to investigate
the receiving filter and sender reputation with Hostinger. Do not blanket
allowlist the domain or disable spam protection as a substitute for diagnosis.

References:

- https://www.hostinger.com/support/8671319-set-up-a-domain-for-hostinger-email-manually/
- https://www.hostinger.com/support/3423286-what-to-do-if-sending-emails-go-to-spam/
- https://support.google.com/mail/answer/81126?hl=en
