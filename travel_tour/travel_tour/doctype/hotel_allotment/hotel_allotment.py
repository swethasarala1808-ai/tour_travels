import frappe
from frappe.model.document import Document

class HotelAllotment(Document):
    def validate(self):
        self.calculate_total_rooms()
    
    def calculate_total_rooms(self):
        total = 0
        for row in self.rooms:
            total += (row.quantity or 0)
        self.total_rooms = total
