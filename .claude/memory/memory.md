# Project memory (Klaimify fork of Buzz, IIRS 2027 event app)
- Branch feature/iirs-event-app. AGPL-3.0 license is kept (user decision). Use Yarn, not npm.
- Participants are imported as submitted Event Tickets (user decision: reuse Event Ticket, no new DocType).
  Extra fields on Event Ticket (registration_id, access_status, external_id, source_system, source_hash, phone,
  organisation, country, photo, user, qr_version...). Ticket type per category (unpublished, free) auto-created.
  Code in buzz/participants: importer (idempotent, key event+source_system+external_id), invites, credentials.
  Imports set flags.skip_ticket_email; source cancellation cancels the ticket.
- Auth: passwordless. Magic link (72h first, 15min later) + email OTP, hashed single-use tokens in cache,
  endpoints in buzz/api/participant_auth.py. Mobile gets `token key:secret` (new sign-in rotates secret).
- Done: Participant Import Batch (CSV), 15-min Frappe sync (site_config participant_sync), signed QR (participants/qr.py),
  scan check-in (idempotent, scanned_at replay), agenda, meetings (slot-row lock, buzz/participants/meetings.py),
  directory (show_in_directory opt-out), leads, announcements, polls, Q&A, face consent + sign-in
  (verifier hook participant_face_verifier or AWS Rekognition via site_config participant_face_aws).
  New DocTypes live in module Participants. APIs in buzz/api/participant_*.py.
- Not done: WhatsApp OTP, push notifications (app polls), per-device tokens, gate in check-in, tests beyond importer.
  No bench in sandbox: code is statically checked only.
