from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from buzz.participants import qr


class TestBadgeToken(FrappeTestCase):
	def test_token_round_trip(self):
		token = qr.build_token("42", 3)
		with patch.object(qr.frappe.db, "get_value", return_value=3):
			self.assertEqual(qr.resolve_ticket(token), "42")

	def test_tampered_signature_is_rejected(self):
		token = qr.build_token("42", 3)
		forged = token[:-1] + ("0" if token[-1] != "0" else "1")
		with self.assertRaises(frappe.ValidationError):
			qr.resolve_ticket(forged)

	def test_ticket_swap_is_rejected(self):
		_prefix, _ticket, version, signature = qr.build_token("42", 3).split(".")
		with self.assertRaises(frappe.ValidationError):
			qr.resolve_ticket(f"B1.43.{version}.{signature}")

	def test_revoked_badge_is_rejected(self):
		token = qr.build_token("42", 1)
		with patch.object(qr.frappe.db, "get_value", return_value=2):
			with self.assertRaises(frappe.ValidationError):
				qr.resolve_ticket(token)

	def test_malformed_token_is_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			qr.resolve_ticket("B1.only-two")

	def test_registration_id_lookup(self):
		with patch.object(qr.frappe.db, "get_value", return_value="42"):
			self.assertEqual(qr.resolve_ticket(" IIRS-DEL-00001 "), "42")
		with patch.object(qr.frappe.db, "get_value", return_value=None):
			with self.assertRaises(frappe.ValidationError):
				qr.resolve_ticket("IIRS-DEL-99999")
