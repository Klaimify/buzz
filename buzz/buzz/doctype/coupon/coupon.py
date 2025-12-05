import frappe
from frappe.model.document import Document
from datetime import date, datetime

class Coupon(Document):
    # begin: auto-generated types
    # This code is auto-generated. Do not modify anything in this block.

    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        from frappe.types import DF

        claimed_coupon: DF.Int
        coupon_code: DF.Data | None
        coupons_granted: DF.Int
        discount_amt: DF.Float
        discount_type: DF.Literal["Amount", "Percentage"]
        event: DF.Link
        valid_from: DF.Date | None
        valid_to: DF.Date | None
    # end: auto-generated types

    def validate(self):
        today = date.today()

        # --- Check for duplicate coupon code ---
        if self.coupon_code:
            existing_coupon = frappe.db.exists(
                "Coupon",
                {
                    "coupon_code": self.coupon_code,
                    "name": ["!=", self.name],
                }
            )
            if existing_coupon:
                frappe.throw(
                    f"Coupon code '{self.coupon_code}' already exists. Please use a different coupon code."
                )

        # --- Convert string dates to date objects ---
        if isinstance(self.valid_from, str):
            self.valid_from = datetime.strptime(self.valid_from, "%Y-%m-%d").date()

        if isinstance(self.valid_to, str):
            self.valid_to = datetime.strptime(self.valid_to, "%Y-%m-%d").date()

        # --- Validate date logic ---
        # if self.valid_from and self.valid_from < today:
        #     frappe.throw("Valid From date cannot be earlier than today.")

        if self.valid_to and self.valid_to <= self.valid_from:
            frappe.throw("Valid To date must be later than Valid From date.")

        # --- Check stay_days (only if field exists) ---
        if hasattr(self, "stay_days") and self.stay_days and self.valid_from and self.valid_to:
            date_difference = (self.valid_to - self.valid_from).days

            if int(self.stay_days) > int(date_difference):
                frappe.throw(
                    f"Stay Days ({self.stay_days}) cannot be more than the difference "
                    f"between Valid From and Valid To ({date_difference} days)."
                )

    def on_trash(self):
        # Cannot delete if coupon is claimed
        if self.claimed_coupon and int(self.claimed_coupon) > 0:
            frappe.throw("Cannot delete a coupon that has been claimed.")


#  API - Validate Coupon (User Side)


@frappe.whitelist()
def validate_coupon_api(coupon_code: str):
    """Validate coupon from user side and return coupon details if valid."""

    if not coupon_code:
        return { "success": False, "message": "Coupon code is required." }
        # frappe.throw("Coupon code is required.")

    # 1) Check if coupon exists
    coupon_name = frappe.db.exists("Coupon", {"coupon_code": coupon_code})
    print(f"[DEBUG] Coupon existence check result: {coupon_name}")

    if not coupon_name:
        return { "success": False, "message": "Invalid coupon code." }
        # frappe.throw("Invalid coupon code.")

    # 2) Load the coupon document
    coupon = frappe.get_doc("Coupon", coupon_name)
    print(f"[DEBUG] Coupon existence check result: {coupon_name}")

    today = date.today()

    # 3) Convert string date formats to date objects (if needed)
    if isinstance(coupon.valid_from, str):
        coupon.valid_from = datetime.strptime(coupon.valid_from, "%Y-%m-%d").date()

    if isinstance(coupon.valid_to, str):
        coupon.valid_to = datetime.strptime(coupon.valid_to, "%Y-%m-%d").date()

    # 4) Check active date range
    if coupon.valid_from and coupon.valid_from > today:
        frappe.throw(f"Coupon is not active yet. Valid from {coupon.valid_from}.")

    if coupon.valid_to and coupon.valid_to < today:
        return { "success": False, "message": "Coupon has expired." }
        # frappe.throw("Coupon has expired.")

    # 5) Check usage limit
    claimed = int(coupon.claimed_coupon or 0)
    allowed = int(coupon.coupons_granted or 0)  # corrected field

    if allowed > 0 and claimed >= allowed:
        print(f"[DEBUG] Coupon usage limit reached: {claimed}/{allowed}")
        return { "success": False, "message": "This coupon has already been fully used." }
        # frappe.throw("This coupon has already been fully used.")

    # 6) Build success response
    return {
        "success": True,
        "name":coupon.name,
        "coupon_code": coupon.coupon_code,
        "discount_type": coupon.discount_type,
        "discount_amt": coupon.discount_amt,
        
    }
