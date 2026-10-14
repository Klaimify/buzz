from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from buzz.participants import meetings


def person(name, event="EV-1", attendee_name="Person"):
	return frappe._dict(name=name, event=event, attendee_name=attendee_name)


class TestMeetings(FrappeTestCase):
	def test_cannot_meet_yourself(self):
		with self.assertRaises(frappe.ValidationError):
			meetings.request_meeting(person("1"), person("1"), "SLOT-1", None)

	def test_participants_must_share_an_event(self):
		with self.assertRaises(frappe.ValidationError):
			meetings.request_meeting(person("1"), person("2", event="EV-2"), "SLOT-1", None)

	def test_busy_participant_is_rejected(self):
		slot = frappe._dict(name="SLOT-1", event="EV-1", tables=2)
		with (
			patch.object(meetings.frappe.db, "get_value", return_value=slot),
			patch.object(meetings, "get_slot_load", return_value=(set(), {"2"})),
		):
			with self.assertRaises(frappe.ValidationError):
				meetings.request_meeting(person("1"), person("2"), "SLOT-1", None)

	def test_full_slot_is_rejected(self):
		slot = frappe._dict(name="SLOT-1", event="EV-1", tables=2)
		with (
			patch.object(meetings.frappe.db, "get_value", return_value=slot),
			patch.object(meetings, "get_slot_load", return_value=({1, 2}, set())),
		):
			with self.assertRaises(frappe.ValidationError):
				meetings.request_meeting(person("1"), person("2"), "SLOT-1", None)

	def test_first_free_table_is_assigned_and_invitee_notified(self):
		slot = frappe._dict(name="SLOT-1", event="EV-1", tables=3)
		meeting_doc = MagicMock()
		meeting_doc.name = "MTG-1"
		with (
			patch.object(meetings.frappe.db, "get_value", return_value=slot),
			patch.object(meetings, "get_slot_load", return_value=({1}, set())),
			patch.object(meetings.frappe, "new_doc", return_value=meeting_doc),
			patch.object(meetings, "enqueue_notification") as notify,
		):
			name = meetings.request_meeting(person("1", attendee_name="Asha"), person("2"), "SLOT-1", "hi")
		self.assertEqual(name, "MTG-1")
		self.assertEqual(meeting_doc.update.call_args.args[0]["table_no"], 2)
		self.assertEqual(notify.call_args.args[0], ["2"])

	def test_only_invitee_can_accept(self):
		meeting = frappe._dict(requester="1", invitee="2", status="Requested", save=MagicMock())
		with patch.object(meetings.frappe, "get_doc", return_value=meeting):
			with self.assertRaises(frappe.PermissionError):
				meetings.respond_to_meeting("MTG-1", "1", "accept")

	def test_accept_updates_status_and_notifies_requester(self):
		meeting = frappe._dict(requester="1", invitee="2", status="Requested", name="MTG-1", save=MagicMock())
		with (
			patch.object(meetings.frappe, "get_doc", return_value=meeting),
			patch.object(meetings.frappe.db, "get_value", return_value="Beena"),
			patch.object(meetings, "enqueue_notification") as notify,
		):
			self.assertEqual(meetings.respond_to_meeting("MTG-1", "2", "accept"), "Accepted")
		self.assertEqual(notify.call_args.args[0], ["1"])

	def test_cannot_cancel_someone_elses_meeting(self):
		meeting = frappe._dict(requester="1", invitee="2", status="Accepted", save=MagicMock())
		with patch.object(meetings.frappe, "get_doc", return_value=meeting):
			with self.assertRaises(frappe.PermissionError):
				meetings.respond_to_meeting("MTG-1", "3", "cancel")
