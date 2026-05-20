import frappe

@frappe.whitelist()
def get_founder_data():
    user_roles = frappe.get_roles(frappe.session.user)
    if not any(r in user_roles for r in ['System Manager', 'Administrator', 'Founder']):
        frappe.throw("Access denied", frappe.PermissionError)

    leads = frappe.get_all('Travel Lead',
        fields=['name','full_name','email_id','mobile_no','status','source',
                'interested_destination','tour_type_pref','travel_month',
                'pax_count','budget_per_person','assigned_consultant','creation'],
        order_by='creation desc', limit=100)

    bookings = frappe.get_all('Booking',
        fields=['name','travel_lead','tour_package','travel_date','status',
                'total_amount','paid_amount','pax_count','creation'],
        order_by='creation desc', limit=100) if frappe.db.exists('DocType','Booking') else []

    packages = frappe.get_all('Tour Package',
        fields=['name','package_name','destination','duration_days','base_price','status'],
        order_by='creation desc', limit=50) if frappe.db.exists('DocType','Tour Package') else []

    customers = frappe.get_all('Travel Lead',
        filters={'status': ['in', ['Booked','Customer']]},
        fields=['name','full_name','email_id','mobile_no','status'],
        order_by='creation desc', limit=100)

    total_revenue = frappe.db.sql(
        "SELECT COALESCE(SUM(paid_amount),0) FROM `tabBooking`"
    )[0][0] if frappe.db.exists('DocType','Booking') else 0

    return {
        'leads': leads,
        'bookings': bookings,
        'packages': packages,
        'customers': customers,
        'team': [],
        'stats': {
            'total_revenue': total_revenue,
            'lead_count': len(leads),
            'open_leads': len([l for l in leads if l.status in ['Open','New','Interested']]),
            'active_bookings': len([b for b in bookings if b.status in ['Confirmed','Active']]),
            'customer_count': len(customers),
        },
        'founder': {
            'name': frappe.db.get_value('User', frappe.session.user, 'full_name') or 'Founder',
            'email': frappe.session.user,
        }
    }

@frappe.whitelist()
def create_lead(**kwargs):
    doc = frappe.get_doc({
        "doctype": "Travel Lead",
        "full_name": kwargs.get('lead_name',''),
        "email_id": kwargs.get('email',''),
        "mobile_no": kwargs.get('mobile',''),
        "status": kwargs.get('status','Open'),
        "interested_destination": kwargs.get('interested_destination',''),
        "tour_type_pref": kwargs.get('tour_type_pref',''),
        "travel_month": kwargs.get('travel_month',''),
        "pax_count": kwargs.get('pax_count',0),
        "budget_per_person": kwargs.get('budget_per_person',0),
        "assigned_consultant": kwargs.get('assigned_consultant',''),
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return {'success': True, 'name': doc.name}

@frappe.whitelist()
def update_lead(**kwargs):
    lead_id = kwargs.get('lead_id') or kwargs.get('name')
    if lead_id and frappe.db.exists('Travel Lead', lead_id):
        doc = frappe.get_doc('Travel Lead', lead_id)
        if kwargs.get('lead_name'): doc.full_name = kwargs['lead_name']
        if kwargs.get('email'):     doc.email_id  = kwargs['email']
        if kwargs.get('mobile'):    doc.mobile_no = kwargs['mobile']
        if kwargs.get('status'):    doc.status    = kwargs['status']
        if kwargs.get('interested_destination'): doc.interested_destination = kwargs['interested_destination']
        if kwargs.get('assigned_consultant'):    doc.assigned_consultant    = kwargs['assigned_consultant']
        doc.save(ignore_permissions=True)
        frappe.db.commit()
        return {'success': True, 'name': doc.name}
    return create_lead(**kwargs)

@frappe.whitelist()
def create_booking(**kwargs):
    if not frappe.db.exists('DocType','Booking'):
        return {'success': False, 'error': 'Booking DocType not found'}
    doc = frappe.get_doc({
        "doctype": "Booking",
        "travel_lead": kwargs.get('travel_lead',''),
        "tour_package": kwargs.get('tour_package',''),
        "travel_date": kwargs.get('travel_date',''),
        "pax_count": kwargs.get('pax_count',1),
        "total_amount": kwargs.get('total_amount',0),
        "status": kwargs.get('status','Pending'),
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return {'success': True, 'name': doc.name}

@frappe.whitelist()
def update_booking_status(booking_name, status):
    if frappe.db.exists('Booking', booking_name):
        doc = frappe.get_doc('Booking', booking_name)
        doc.status = status
        doc.save(ignore_permissions=True)
        frappe.db.commit()
        return {'success': True}
    return {'success': False, 'error': 'Not found'}

@frappe.whitelist()
def record_payment(**kwargs):
    booking_name = kwargs.get('booking_name')
    amount = float(kwargs.get('amount', 0))
    if booking_name and frappe.db.exists('Booking', booking_name):
        doc = frappe.get_doc('Booking', booking_name)
        doc.paid_amount = float(doc.paid_amount or 0) + amount
        doc.save(ignore_permissions=True)
        frappe.db.commit()
        return {'success': True}
    return {'success': False, 'error': 'Not found'}

@frappe.whitelist()
def save_package(**kwargs):
    if not frappe.db.exists('DocType','Tour Package'):
        return {'success': False, 'error': 'DocType not found'}
    pkg_id = kwargs.get('pkg_id')
    doc = frappe.get_doc('Tour Package', pkg_id) if pkg_id and frappe.db.exists('Tour Package', pkg_id) else frappe.new_doc('Tour Package')
    for k, v in kwargs.items():
        if k != 'pkg_id' and hasattr(doc, k):
            setattr(doc, k, v)
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return {'success': True, 'name': doc.name}

@frappe.whitelist()
def update_visa_status(booking_name, pax_name, visa_status):
    if frappe.db.exists('DocType','Visa Application'):
        visas = frappe.get_all('Visa Application',
            filters={'booking': booking_name, 'pax_name': pax_name}, pluck='name')
        if visas:
            doc = frappe.get_doc('Visa Application', visas[0])
            doc.status = visa_status
            doc.save(ignore_permissions=True)
            frappe.db.commit()
            return {'success': True}
    return {'success': False, 'error': 'Not found'}

@frappe.whitelist()
def delete_record(doctype, record_name):
    allowed = ['Travel Lead','Booking','Tour Package','Visa Application']
    if doctype not in allowed:
        return {'success': False, 'error': 'Not allowed'}
    if frappe.db.exists(doctype, record_name):
        frappe.delete_doc(doctype, record_name, ignore_permissions=True)
        frappe.db.commit()
        return {'success': True}
    return {'success': False, 'error': 'Not found'}
