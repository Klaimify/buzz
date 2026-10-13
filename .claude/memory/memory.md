# Project memory (Klaimify fork of Buzz, IIRS 2027 event app)
- Branch feature/iirs-event-app. AGPL-3.0 license is kept (user decision). Use Yarn, not npm.
- New module `Participants` (buzz/participants): Event Participant DocType (separate from Event Ticket),
  idempotent importer (key: event, source_system, external_id; source_hash), invite waves, credentials.
- Auth: passwordless. Magic link (72h first, 15min later) + email OTP, hashed single-use tokens in cache,
  endpoints in buzz/api/participant_auth.py. Mobile gets `token key:secret` (new sign-in rotates secret).
- Not yet done: Import Batch DocType/CSV upload UI, Frappe sync job, WhatsApp OTP, face sign-in, consent record,
  QR token, check-in, hooks.py scheduler entry. No bench in sandbox: code is statically checked only.
