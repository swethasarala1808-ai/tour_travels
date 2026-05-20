import frappe

@frappe.whitelist()
def get_founder_data():
    if frappe.session.user == 'Guest':
        frappe.throw("Not permitted", frappe.PermissionError)
    
    data = {
        'leads': frappe.get_all('Travel Lead',
            fields=['name','full_name','mobile_no','email_id','status','source'],
            order_by='creation desc', limit=100),
        'bookings': frappe.get_all('Booking',
            fields=['name','travel_lead','tour_package','travel_date','status','total_amount'],
            order_by='creation desc', limit=100),
        'packages': frappe.get_all('Tour Package',
            fields=['name','package_name','destination'],
            order_by='creation desc', limit=100),
        'visa_applications': frappe.get_all('Visa Application',
            fields=['name','pax_name','destination','status'],
            order_by='creation desc', limit=100),
    }
    return data

@frappe.whitelist()
def create_lead(**kwargs):
    if frappe.session.user == 'Guest':
        frappe.throw("Not permitted", frappe.PermissionError)
    doc = frappe.get_doc(dict(doctype='Travel Lead', **kwargs))
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return {'success': True, 'name': doc.name}

@frappe.whitelist()
def create_booking(**kwargs):
    if frappe.session.user == 'Guest':
        frappe.throw("Not permitted", frappe.PermissionError)
    doc = frappe.get_doc(dict(doctype='Booking', **kwargs))
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return {'success': True, 'name': doc.name}

@frappe.whitelist()
def save_package(**kwargs):
    if frappe.session.user == 'Guest':
        frappe.throw("Not permitted", frappe.PermissionError)
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
