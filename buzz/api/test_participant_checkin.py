from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from buzz.api import participant_checkin

TICKET = frappe._dict(
	registration_id="IIRS-DEL-00001", attendee_name="Asha", ticket_type="7", event="EV-1", organisation="Org"
)


class TestScanCheckin(FrappeTestCase):
	def run_scan(self, existing, gate=None):
		checkin_doc = MagicMock(creation="2027-01-10 09:00:00")
		with (
			patch.object(participant_checkin.frappe, "only_for"),
			patch.object(participant_checkin, "resolve_ticket", return_value="42"),
			patch.object(participant_checkin.frappe.db, "get_value", side_effect=[TICKET, "Delegate", existing]),
			patch.object(participant_checkin.frappe, "new_doc", return_value=checkin_doc),
		):
			result = participant_checkin.scan_checkin("code", "2027-01-10T09:00:00", gate)
		return result, checkin_doc

	def test_first_scan_records_gate(self):
		result, checkin_doc = self.run_scan(existing=None, gate=" Gate A ")
		self.assertEqual(result["status"], "checked_in")
		self.assertEqual(result["gate"], "Gate A")
		self.assertEqual(checkin_doc.gate, "Gate A")
		checkin_doc.submit.assert_called_once()

	def test_repeat_scan_is_idempotent_and_keeps_first_gate(self):
		existing = frappe._dict(creation="2027-01-10 08:00:00", gate="Gate A")
		result, checkin_doc = self.run_scan(existing=existing, gate="Gate B")
		self.assertEqual(result["status"], "already_checked_in")
		self.assertEqual(result["gate"], "Gate A")
		checkin_doc.submit.assert_not_called()

	def test_gate_is_optional(self):
		result, _checkin_doc = self.run_scan(existing=None)
		self.assertIsNone(result["gate"])
