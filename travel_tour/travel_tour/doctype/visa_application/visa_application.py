import frappe
from frappe.model.document import Document
from frappe.utils import date_diff, add_days, today
from frappe import _

class VisaApplication(Document):
    def validate(self):
        self.populate_document_checklist()
        self.check_passport_validity()
        self.set_submission_deadline()
        self.set_all_docs_collected()

    def populate_document_checklist(self):
        """
        Auto-populates document checklist based on country config.
        """
        if not self.destination_country or not self.visa_type:
            return

        if not self.document_checklist:
            config_name = frappe.db.get_value('Visa Country Config', 
                {'country': self.destination_country, 'visa_type': self.visa_type})
            
            if config_name:
                config = frappe.get_doc('Visa Country Config', config_name)
                for req_doc in config.required_documents:
                    self.append('document_checklist', {
                        'document_name': req_doc.document_name,
                        'is_mandatory': req_doc.is_mandatory,
                        'collected': 0,
                        'verified': 0
                    })

    def check_passport_validity(self):
        """
        Warning if passport expires within 6 months of departure.
        """
        if self.passport_expiry and self.departure_date:
            days = date_diff(self.passport_expiry, self.departure_date)
            if days < 180:
                frappe.msgprint(
                    _("WARNING: Passport expires in {0} days from departure. Most countries require 6 months validity.")
                    .format(days), indicator='red', alert=True)

    def set_submission_deadline(self):
        """
        Set deadline based on country processing days.
        """
        if self.departure_date:
            processing_days = frappe.db.get_value('Visa Country Config', 
                {'country': self.destination_country, 'visa_type': self.visa_type}, 
                'processing_days') or 15
            
            # Deadline is processing_days + 3 days buffer before departure
            self.submission_deadline = add_days(self.departure_date, -(processing_days + 3))

    def set_all_docs_collected(self):
        """
        Checks if all mandatory documents have been collected.
        """
        mandatory_pending = [d for d in self.document_checklist if d.is_mandatory and not d.collected]
        self.all_docs_collected = 1 if not mandatory_pending else 0

    def on_submit(self):
        if self.status == 'Approved':
            self.create_delivery_log()

    def create_delivery_log(self):
        log = frappe.get_doc({
            'doctype': 'Visa Delivery Log',
            'visa_application': self.name,
            'applicant_name': self.applicant_name,
            'delivery_mode': 'Digital'
        })
        log.insert(ignore_permissions=True)
