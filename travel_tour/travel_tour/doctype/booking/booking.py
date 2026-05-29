import frappe
from frappe.model.document import Document
from frappe.utils import flt

class Booking(Document):
    def validate(self):
        self.calculate_totals()

    def calculate_totals(self):
        if not self.tour_package:
            return

        pkg = frappe.get_doc('Tour Package', self.tour_package)

        # Try pricing slab first
        price_info = None
        try:
            price_info = pkg.get_price_for_pax(self.total_pax)
        except Exception:
            price_info = None

        if price_info and price_info.get('total'):
            self.base_amount = flt(price_info['total'])
        else:
            # Fallback: use existing base_amount or 0
            if not self.base_amount:
                self.base_amount = 0

        # Addons
        addons_total = sum(flt(r.amount) for r in (self.addons or []))

        # Taxable Amount
        taxable_amount = flt(self.base_amount) + addons_total - flt(self.discount_amount)

        # GST 5%
        self.gst_amount = taxable_amount * 0.05

        # TCS for International above 7L
        self.tcs_amount = 0
        if pkg.tour_type == 'International' and taxable_amount > 700000:
            self.tcs_amount = taxable_amount * 0.05

        # Grand Total
        self.grand_total = taxable_amount + self.gst_amount + self.tcs_amount

    def on_submit(self):
        pass
