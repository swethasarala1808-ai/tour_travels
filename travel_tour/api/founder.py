import frappe

@frappe.whitelist()
def get_founder_data():
    frappe.only_for(['Founder', 'System Manager'])
    
    data = {
        'leads': frappe.get_all('Travel Lead', fields=['name','full_name','mobile_no','email_id','status'], limit=50),
        'bookings': frappe.get_all('Booking', fields=['name','travel_lead','tour_package','travel_date','status','total_amount'], limit=50),
        'packages': frappe.get_all('Tour Package', fields=['name','package_name','destination','price'], limit=50),
        'visa_applications': frappe.get_all('Visa Application', fields=['name','pax_name','destination','status'], limit=50),
    }
    return data

@frappe.whitelist()
def create_lead(full_name, mobile_no, email_id=None, status='Open', remarks=None):
    frappe.only_for(['Founder', 'System Manager'])
    doc = frappe.get_doc({
        'doctype': 'Travel Lead',
        'full_name': full_name,
        'mobile_no': mobile_no,
        'email_id': email_id,
        'status': status,
        'remarks': remarks
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return {'success': True, 'name': doc.name}

@frappe.whitelist()
def create_booking(**kwargs):
    frappe.only_for(['Founder', 'System Manager'])
    doc = frappe.get_doc(dict(doctype='Booking', **kwargs))
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return {'success': True, 'name': doc.name}

@frappe.whitelist()
def save_package(**kwargs):
    frappe.only_for(['Founder', 'System Manager'])
    name = kwargs.pop('name', None)
    if name and frappe.db.exists('Tour Package', name):
        doc = frappe.get_doc('Tour Package', name)
        doc.update(kwargs)
        doc.save(ignore_permissions=True)
    else:
        doc = frappe.get_doc(dict(doctype='Tour Package', **kwargs))
        doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return {'success': True, 'name': doc.name}
