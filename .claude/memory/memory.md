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
- Push (Expo): Participant Device doctype (one row per token), api/participant_notifications.py register/unregister,
  participants/push.py (batches of 100, prunes DeviceNotRegistered). Triggers: Participant Announcement after_insert hook,
  meeting request/respond. Mobile registers after sign-in, unregisters on sign-out.
- WhatsApp OTP: request_sign_in(email, channel="whatsapp") uses WhatsApp Cloud API authentication template, config in
  site_config participant_whatsapp {phone_number_id, access_token, template_name, language}; falls back to email on failure.
  Email sending lives in participants/invites.py send_sign_in_email.
- Gate check-in: Event Check In.gate field; scan_checkin(code, scanned_at, gate) (first scan of the day keeps its gate),
  get_gate_stats for the scanner screen.
- Tests: buzz/participants/test_*.py and buzz/api/test_participant_checkin.py (mock based). Ran only under a hand-made
  frappe stub, NOT on a real bench: run `bench --site <site> run-tests --app buzz --module buzz.participants.test_qr` etc.
  Mobile: `yarn test` (real jest run).
- Fixed: doctype controller files had unindented `pass` (IndentationError).
- Not done: per-device session tokens (new sign-in replaces the API secret), push needs EAS project + FCM/APNs creds,
  WhatsApp template must be approved by Meta. No bench in sandbox.
