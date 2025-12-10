# Copyright (c) 2025, BWH Studios and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class Section(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from buzz.buzz.doctype.past_events.past_events import PastEvents
		from buzz.buzz.doctype.website_sub_section.website_sub_section import websiteSubSection
		from frappe.types import DF

		heading: DF.Data | None
		items: DF.Table[websiteSubSection]
		past_events: DF.Table[PastEvents]
		section_key: DF.Data | None
		sub_heading: DF.Data | None
		title: DF.Data | None
	# end: auto-generated types
	pass
