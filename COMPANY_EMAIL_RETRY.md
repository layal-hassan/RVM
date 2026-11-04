# Company email retries

All existing company-notification paths use the durable outbox through
`send_company_email`. Customer confirmations and invoice emails are separate
and are never retried by this worker.

The complete original MIME message, including attachments, recipients and
Reply-To, is saved in the database **before** SMTP configuration or login.
The first attempt is immediate. After a failure, retries wait 1 minute,
5 minutes, 15 minutes, 1 hour and 4 hours respectively (six attempts total).
Exhausted messages remain visible as **Needs attention** in Automated Emails.
Successful messages are marked **Accepted by mail server** and their saved
body/attachments are cleared. This status does not prove Inbox delivery.

Workers claim rows atomically with a lease, so concurrent workers do not
normally send the same row. An expired lease is recoverable after a process
crash. SMTP has no exactly-once delivery guarantee: a crash or lost connection
after remote acceptance but before the database update can result in a
duplicate. The original Message-ID is retained for every attempt.

Failures from before migration 0064 have no stored original message or
reliable delivery status. They are not reconstructed or resent automatically.

## Local operation

Apply migration 0064, then use one of:

```powershell
python manage.py retry_company_emails --limit 50
python manage.py retry_company_emails --watch
```

The first command processes one due batch. The second keeps checking every
30 seconds. Do not run these commands in a test environment with real SMTP
unless you intend to send its pending company messages.

## Production deployment

Use the active production virtualenv in `/var/www/rwmel`. The `service_manage.py`
wrapper obtains the actual `rwmel` systemd environment and PostgreSQL settings;
plain `manage.py` from the login shell can select a different database.

Publish the Python files, template and migration together, then run:

```bash
python service_manage.py backup_database
python service_manage.py migrate --plan
```

Review the plan, then apply it. If the VPS has an additional migration branch,
resolve that migration graph as described in EMAIL_DELIVERABILITY.md before
applying migrations. Do not delete migration history or use `--fake`.

```bash
python service_manage.py migrate
python service_manage.py check
sudo systemctl restart rwmel
```

Generate the worker unit **on the VPS using the same virtualenv**, so it
contains the actual Python path, project directory and service user. This
command only prints a unit; it neither installs a service nor sends messages.

```bash
python service_manage.py retry_company_emails --print-systemd-unit > /tmp/rwmel-company-email-retry.service
cat /tmp/rwmel-company-email-retry.service
sudo systemd-analyze verify /tmp/rwmel-company-email-retry.service
sudo install -m 644 /tmp/rwmel-company-email-retry.service /etc/systemd/system/rwmel-company-email-retry.service
sudo systemctl daemon-reload
sudo systemctl enable --now rwmel-company-email-retry
sudo systemctl is-active rwmel-company-email-retry
```

The worker uses `service_manage.py` each time systemd starts it, preserving the
production database and SMTP environment. It restarts after errors and starts
after server reboots. There is no separate queue service or dependency upgrade.

Verify pending/accepted status in **Automated Emails → Company email delivery**.
Inspect operational logs with:

```bash
sudo journalctl -u rwmel-company-email-retry -n 50 --no-pager
```

If repeated failures reach **Needs attention**, correct the reported account or
network issue before an operator explicitly requeues a reviewed message. The
worker does not reset exhausted attempts or retry accepted messages.

When rolling application code back, stop the new worker first. Keep the outbox
table and pending records intact; reverting the additive migration would delete
the retry history and any unsent payloads.
