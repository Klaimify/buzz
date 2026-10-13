# Copyright (c) 2026, Klaimify and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import make_autoname

CATEGORY_CODES = {
	"International Buyer": "B",
	"Domestic Buyer": "N",
	"Exhibitor Rep": "E",
	"Delegate": "D",
	"Speaker": "S",
	"Sponsor": "P",
	"Media": "M",
	"Staff": "F",
}


class EventParticipant(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		activated_on: DF.Datetime | None
		category: DF.Literal[
			"International Buyer",
			"Domestic Buyer",
			"Exhibitor Rep",
			"Delegate",
			"Speaker",
			"Sponsor",
			"Media",
			"Staff",
		]
		country: DF.Data | None
		email: DF.Data
		event: DF.Link
		external_id: DF.Data
		face_signin_enabled: DF.Check
		full_name: DF.Data
		invite_count: DF.Int
		invited_on: DF.Datetime | None
		organisation: DF.Data | None
		phone: DF.Data | None
		photo: DF.AttachImage | None
		qr_version: DF.Int
		registration_id: DF.Data | None
		source_hash: DF.Data | None
		source_system: DF.Data
		status: DF.Literal["Imported", "Invited", "Activated", "Disabled"]
		user: DF.Link | None
	# end: auto-generated types

	def autoname(self):
		# Registration IDs look like IIRS27-B-00421 (event prefix, category letter, running number).
		event_prefix = frappe.db.get_value("Buzz Event", self.event, "route") or self.event
		event_prefix = "".join(char for char in str(event_prefix).upper() if char.isalnum())[:12]
		category_code = CATEGORY_CODES.get(self.category, "X")
		self.registration_id = make_autoname(f"{event_prefix}-{category_code}-.#####")
		self.name = self.registration_id

	def validate(self):
		self.email = (self.email or "").strip().lower()
		self.validate_unique_source_record()

	def validate_unique_source_record(self):
		duplicate = frappe.db.exists(
			"Event Participant",
			{
				"event": self.event,
				"source_system": self.source_system,
				"external_id": self.external_id,
				"name": ("!=", self.name),
			},
		)
		if duplicate:
			frappe.throw(
				_("Participant {0} already exists for this event and source record").format(duplicate)
			)
