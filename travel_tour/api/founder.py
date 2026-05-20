import frappe

@frappe.whitelist()
def get_founder_data():
    if frappe.session.user == 'Guest':
        frappe.throw("Login required", frappe.AuthenticationError)

    leads = frappe.get_all('Travel Lead',
        fields=['name','full_name','email_id','mobile_no','status',
                'source','suggested_package','pax_count',
                'preferred_month','assigned_consultant','creation'],
        order_by='creation desc', limit=100)

    bookings = []
    if frappe.db.table_exists('tabBooking'):
        bookings = frappe.get_all('Booking',
            fields=['name','travel_lead','tour_package','travel_date',
                    'status','total_amount','paid_amount','pax_count','creation'],
            order_by='creation desc', limit=100)

    packages = []
    if frappe.db.table_exists('tabTour Package'):
        packages = frappe.get_all('Tour Package',
            fields=['name','package_name','destination','duration_days',
                    'base_price','status','creation'],
            order_by='creation desc', limit=50)

    total_revenue = 0
    balance_due = 0
    active_bookings = 0
    if frappe.db.table_exists('tabBooking'):
        try:
            r = frappe.db.sql("""
                SELECT
                    COALESCE(SUM(total_amount),0) as revenue,
                    COALESCE(SUM(total_amount - COALESCE(paid_amount,0)),0) as balance,
                    COUNT(CASE WHEN status IN ('Confirmed','Active') THEN 1 END) as active
                FROM `tabBooking`
            """, as_dict=True)
            if r:
                total_revenue = float(r[0].revenue or 0)
                balance_due = float(r[0].balance or 0)
                active_bookings = int(r[0].active or 0)
        except Exception:
            pass

    open_leads = len([l for l in leads if l.status in ['Open','New','Interested','Contacted']])
    founder_name = frappe.db.get_value('User', frappe.session.user, 'full_name') or 'Founder'

    return {
        'leads': leads,
        'bookings': bookings,
        'packages': packages,
        'customers': [l for l in leads if l.status in ['Booked','Customer']],
        'team': [],
        'settings': {},
        'stats': {
            'total_revenue': total_revenue,
            'balance_due': balance_due,
            'active_bookings': active_bookings,
            'open_leads': open_leads,
            'lead_count': len(leads),
            'customer_count': len([l for l in leads if l.status in ['Booked','Customer']]),
            'departures_30d': 0,
        },
        'founder': {
            'name': founder_name,
            'email': frappe.session.user,
            'role': 'Founder & CEO',
        }
    }

@frappe.whitelist()
def create_lead(**kwargs):
    doc = frappe.get_doc({
        "doctype": "Travel Lead",
        "full_name": kwargs.get('lead_name') or kwargs.get('full_name',''),
        "email_id": kwargs.get('email',''),
        "mobile_no": kwargs.get('mobile',''),
        "status": kwargs.get('status','Open'),
        "source": kwargs.get('source',''),
        "suggested_package": kwargs.get('interested_destination',''),
        "pax_count": int(kwargs.get('pax_count') or 0),
        "preferred_month": kwargs.get('travel_month',''),
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
        field_map = {
            'lead_name': 'full_name', 'full_name': 'full_name',
            'email': 'email_id', 'mobile': 'mobile_no',
            'status': 'status', 'source': 'source',
            'interested_destination': 'suggested_package',
            'assigned_consultant': 'assigned_consultant',
            'pax_count': 'pax_count', 'travel_month': 'preferred_month',
        }
        for k, field in field_map.items():
            if kwargs.get(k) is not None:
                setattr(doc, field, kwargs[k])
        doc.save(ignore_permissions=True)
        frappe.db.commit()
        return {'success': True, 'name': doc.name}
    return create_lead(**kwargs)

@frappe.whitelist()
def create_booking(**kwargs):
    if not frappe.db.table_exists('tabBooking'):
        return {'success': False, 'error': 'Booking module not ready'}
    doc = frappe.get_doc({
        "doctype": "Booking",
        "travel_lead": kwargs.get('travel_lead',''),
        "tour_package": kwargs.get('tour_package',''),
        "travel_date": kwargs.get('travel_date',''),
        "pax_count": int(kwargs.get('pax_count') or 1),
        "total_amount": float(kwargs.get('total_amount') or 0),
        "status": kwargs.get('status','Pending'),
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return {'success': True, 'name': doc.name}

@frappe.whitelist()
def update_booking_status(booking_name, status):
    if frappe.db.exists('Booking', booking_name):
        frappe.db.set_value('Booking', booking_name, 'status', status)
        frappe.db.commit()
        return {'success': True}
    return {'success': False, 'error': 'Not found'}

@frappe.whitelist()
def record_payment(**kwargs):
    bname = kwargs.get('booking_name')
    amount = float(kwargs.get('amount') or 0)
    if bname and frappe.db.exists('Booking', bname):
        current = float(frappe.db.get_value('Booking', bname, 'paid_amount') or 0)
        frappe.db.set_value('Booking', bname, 'paid_amount', current + amount)
        frappe.db.commit()
        return {'success': True}
    return {'success': False, 'error': 'Booking not found'}

@frappe.whitelist()
def save_package(**kwargs):
    if not frappe.db.table_exists('tabTour Package'):
        return {'success': False, 'error': 'Tour Package not available'}
    pkg_id = kwargs.get('pkg_id') or kwargs.get('name')
    if pkg_id and frappe.db.exists('Tour Package', pkg_id):
        doc = frappe.get_doc('Tour Package', pkg_id)
    else:
        doc = frappe.new_doc('Tour Package')
    for k, v in kwargs.items():
        if k not in ('pkg_id','name') and hasattr(doc, k):
            setattr(doc, k, v)
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return {'success': True, 'name': doc.name}

@frappe.whitelist()
def update_visa_status(booking_name, pax_name, visa_status):
    if frappe.db.table_exists('tabVisa Application'):
        visas = frappe.get_all('Visa Application',
            filters={'booking': booking_name, 'pax_name': pax_name}, pluck='name')
        if visas:
            frappe.db.set_value('Visa Application', visas[0], 'status', visa_status)
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
