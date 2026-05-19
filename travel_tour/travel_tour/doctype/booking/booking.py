import frappe
from frappe.model.document import Document
from frappe.utils import flt

class Booking(Document):
    def validate(self):
        self.calculate_totals()

    def calculate_totals(self):
        if not self.tour_package:
            return

        # 1. Base Amount from Package
        pkg = frappe.get_doc('Tour Package', self.tour_package)
        price_info = pkg.get_price_for_pax(self.total_pax)
        self.base_amount = flt(price_info['total'])

        # 2. Addons
        addons_total = sum(flt(r.amount) for r in self.addons)

        # 3. Taxable Amount
        taxable_amount = self.base_amount + addons_total - flt(self.discount_amount)

        # 4. GST (Assuming 5% for now, can be configured in settings later)
        self.gst_amount = taxable_amount * 0.05

        # 5. TCS (Assuming 5% for International packages above 7L, as per doc)
        self.tcs_amount = 0
        if pkg.tour_type == 'International' and taxable_amount > 700000:
            self.tcs_amount = taxable_amount * 0.05

        # 6. Grand Total
        self.grand_total = taxable_amount + self.gst_amount + self.tcs_amount

    def on_submit(self):
        # Triggered from hooks or locally
        pass
