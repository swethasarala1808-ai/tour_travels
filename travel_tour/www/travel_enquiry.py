import frappe

def get_context(context):
    context.no_cache = 1
    context.user = frappe.session.user
    context.is_guest = frappe.session.user == 'Guest'
    context.user_name = '' if context.is_guest else (frappe.db.get_value('User', frappe.session.user, 'full_name') or '')

@frappe.whitelist()
def get_portal_data():
    if frappe.session.user == 'Guest':
        frappe.throw("Please login", frappe.AuthenticationError)
    lead = frappe.db.get_value('Travel Lead',
        {'email_id': frappe.session.user},
        ['name','full_name','mobile_no','status','email_id',
         'interested_destination','tour_type_pref','travel_month','pax_count'],
        as_dict=True)
    if not lead:
        return None
    bookings = frappe.get_all('Booking',
        filters={'travel_lead': lead.name},
        fields=['name','tour_package','travel_date','status','total_amount','paid_amount','pax_count'],
        order_by='creation desc') if frappe.db.exists('DocType','Booking') else []
    for b in bookings:
        b['balance'] = float(b.get('total_amount') or 0) - float(b.get('paid_amount') or 0)
        b['itinerary'] = []
    visas = frappe.get_all('Visa Application',
        filters={'booking': ['in', [b.name for b in bookings]]},
        fields=['name','booking','pax_name','passport_no','destination','status']
    ) if frappe.db.exists('DocType','Visa Application') and bookings else []
    return {'lead': lead, 'bookings': bookings, 'visas': visas, 'cur': bookings[0] if bookings else None}

@frappe.whitelist(allow_guest=True)
def submit_enquiry(**kwargs):
    doc = frappe.get_doc({
        "doctype": "Travel Lead",
        "full_name": kwargs.get('full_name',''),
        "email_id": kwargs.get('email',''),
        "mobile_no": kwargs.get('mobile',''),
        "status": "New",
        "interested_destination": kwargs.get('destination',''),
        "pax_count": kwargs.get('pax_count', 1),
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return {'success': True, 'name': doc.name}
