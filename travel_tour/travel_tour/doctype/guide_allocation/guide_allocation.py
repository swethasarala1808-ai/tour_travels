import frappe
from frappe.model.document import Document
from frappe import _

class GuideAllocation(Document):
    def validate(self):
        self.check_guide_conflict()

    def check_guide_conflict(self):
        """
        Check if the selected guide is already allocated for overlapping dates.
        """
        conflict = frappe.db.exists('Guide Allocation', {
            'guide': self.guide,
            'departure_date': ['<=', self.return_date],
            'return_date': ['>=', self.departure_date],
            'name': ['!=', self.name],
            'docstatus': ['!=', 2] # Not cancelled
        })
        
        if conflict:
            frappe.throw(_("Guide {0} is already allocated for booking {1} during this period.")
                         .format(self.guide, conflict))
