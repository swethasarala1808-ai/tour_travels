import frappe
from frappe.model.document import Document

class TourPackage(Document):
    def validate(self):
        self.duration_days = (self.duration_nights or 0) + 1
        self.validate_pricing_slabs()

    def validate_pricing_slabs(self):
        for row in self.pricing_table:
            if row.min_pax and row.max_pax and row.min_pax > row.max_pax:
                frappe.throw(f'Row {row.idx}: Min Pax cannot be greater than Max Pax')

    @frappe.whitelist()
    def get_price_for_pax(self, pax_count):
        pax_count = int(pax_count)
        for row in self.pricing_table:
            min_pax = row.min_pax or 0
            max_pax = row.max_pax or 9999
            if min_pax <= pax_count <= max_pax:
                return {
                    'per_person': row.per_person_price,
                    'total': row.per_person_price * pax_count
                }
        frappe.throw(f'No pricing slab found for {pax_count} pax in package {self.name}')
