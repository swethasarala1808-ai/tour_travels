import frappe
from frappe.model.document import Document
from frappe.utils import flt

class VisaFeeBilling(Document):
    def validate(self):
        self.calculate_totals()

    def calculate_totals(self):
        self.gst_amount = flt(self.service_charge) * 0.18 # Assuming 18% GST on service charge
        self.grand_total = flt(self.embassy_fee) + flt(self.service_charge) + self.gst_amount

    def on_submit(self):
        self.create_sales_invoice()

    def create_sales_invoice(self):
        """
        Creates a Sales Invoice in ERPNext for the visa billing.
        """
        si = frappe.new_doc('Sales Invoice')
        si.customer = self.customer
        si.append('items', {
            'item_code': 'VISA-SERVICE', # Assumed to exist per user confirmation
            'qty': 1,
            'rate': self.grand_total,
            'description': f"Visa Processing Fee - {self.visa_application or self.booking}"
        })
        si.insert(ignore_permissions=True)
        si.submit()
        self.db_set('sales_invoice', si.name)
