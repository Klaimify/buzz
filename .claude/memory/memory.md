# Project memory (Klaimify fork of Buzz, IIRS 2027 event app)
- Branch feature/iirs-event-app. AGPL-3.0 license is kept (user decision). Use Yarn, not npm.
- Participants are imported as submitted Event Tickets (user decision: reuse Event Ticket, no new DocType).
  Extra fields on Event Ticket (registration_id, access_status, external_id, source_system, source_hash, phone,
  organisation, country, photo, user, qr_version...). Ticket type per category (unpublished, free) auto-created.
  Code in buzz/participants: importer (idempotent, key event+source_system+external_id), invites, credentials.
  Imports set flags.skip_ticket_email; source cancellation cancels the ticket.
- Auth: passwordless. Magic link (72h first, 15min later) + email OTP, hashed single-use tokens in cache,
  endpoints in buzz/api/participant_auth.py. Mobile gets `token key:secret` (new sign-in rotates secret).
- Not yet done: Import Batch DocType/CSV upload UI, Frappe sync job, WhatsApp OTP, face sign-in, consent record,
  QR token, check-in, hooks.py scheduler entry. No bench in sandbox: code is statically checked only.
