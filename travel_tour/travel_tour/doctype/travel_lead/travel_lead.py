import frappe
from frappe.model.document import Document

class TravelLead(Document):
    def after_insert(self):
        self.assign_consultant_round_robin()
        # self.send_whatsapp_ack() # Placeholder for later

    def assign_consultant_round_robin(self):
        # Find users with 'Travel Consultant' role
        consultants = frappe.get_all('Has Role',
            filters={'role': 'Travel Consultant'},
            pluck='parent'
        )
        if not consultants:
            return

        # Simple round-robin: assign to consultant with fewest active leads
        loads = []
        for c in consultants:
            count = frappe.db.count('Travel Lead', {
                'assigned_consultant': c,
                'status': 'Open'
            })
            loads.append((c, count))

        # Sort by load and pick the one with minimum
        if loads:
            self.db_set('assigned_consultant', min(loads, key=lambda x: x[1])[0])

    @frappe.whitelist()
    def convert_to_booking(self):
        booking = frappe.new_doc('Booking')
        booking.customer = self.customer
        booking.tour_package = self.suggested_package
        booking.total_pax = self.pax_count or 1
        booking.sales_consultant = self.assigned_consultant
        booking.insert(ignore_permissions=True)

        self.db_set('status', 'converted')
        self.db_set('converted_booking', booking.name)

        return booking.name
