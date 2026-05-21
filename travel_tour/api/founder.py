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

    # FIXED: use table_exists('Tour Package') not 'tabTour Package'
    bookings = []
    if frappe.db.table_exists('Booking'):
        bookings = frappe.get_all('Booking',
            fields=['name','customer','customer_mobile','tour_package',
                    'departure_date','total_pax','sales_consultant',
                    'base_amount','discount_amount','gst_amount',
                    'tcs_amount','grand_total','creation'],
            order_by='creation desc', limit=100)

    packages = []
    if frappe.db.table_exists('Tour Package'):
        packages = frappe.get_all('Tour Package',
            fields=['name','package_name','destination','tour_type',
                    'duration_days','duration_nights','visa_required','creation'],
            order_by='creation desc', limit=50)

    total_revenue = 0
    active_bookings = 0
    if frappe.db.table_exists('Booking'):
        try:
            r = frappe.db.sql("""
                SELECT COALESCE(SUM(grand_total),0) as revenue, COUNT(*) as active
                FROM `tabBooking`
            """, as_dict=True)
            if r:
                total_revenue = float(r[0].revenue or 0)
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
            'balance_due': 0,
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
        "full_name": kwargs.get('full_name') or kwargs.get('lead_name',''),
        "email_id": kwargs.get('email_id') or kwargs.get('email',''),
        "mobile_no": kwargs.get('mobile_no') or kwargs.get('mobile',''),
        "status": kwargs.get('status','Open'),
        "source": kwargs.get('source',''),
        "suggested_package": kwargs.get('suggested_package') or kwargs.get('interested_destination',''),
        "pax_count": int(kwargs.get('pax_count') or 0),
        "preferred_month": kwargs.get('preferred_month') or kwargs.get('travel_month',''),
        "assigned_consultant": kwargs.get('assigned_consultant',''),
        "remarks": kwargs.get('remarks',''),
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
            'full_name': 'full_name', 'lead_name': 'full_name',
            'email_id': 'email_id', 'email': 'email_id',
            'mobile_no': 'mobile_no', 'mobile': 'mobile_no',
            'status': 'status', 'source': 'source',
            'suggested_package': 'suggested_package',
            'interested_destination': 'suggested_package',
            'assigned_consultant': 'assigned_consultant',
            'pax_count': 'pax_count',
            'preferred_month': 'preferred_month',
            'travel_month': 'preferred_month',
            'remarks': 'remarks',
        }
        for k, field in field_map.items():
            if kwargs.get(k) is not None:
                setattr(doc, field, kwargs[k])
        doc.save(ignore_permissions=True)
        frappe.db.commit()
        return {'success': True, 'name': doc.name}
    return create_lead(**kwargs)

@frappe.whitelist()
def save_package(**kwargs):
    # FIXED: correct table check
    if not frappe.db.table_exists('Tour Package'):
        return {'success': False, 'error': 'Tour Package table not found'}

    pkg_id = kwargs.get('pkg_id') or kwargs.get('name')
    if pkg_id and frappe.db.exists('Tour Package', pkg_id):
        doc = frappe.get_doc('Tour Package', pkg_id)
    else:
        doc = frappe.new_doc('Tour Package')

    # Map fields - tour_type must be Domestic or International
    tour_type = kwargs.get('tour_type','Domestic')
    if tour_type not in ('Domestic','International'):
        tour_type = 'Domestic'

    if kwargs.get('package_name'):
        doc.package_name = kwargs['package_name']
    doc.tour_type = tour_type
    if kwargs.get('destination'):
        doc.destination = kwargs['destination']
    if kwargs.get('duration_days'):
        doc.duration_days = int(kwargs['duration_days'])
    if kwargs.get('duration_nights') or kwargs.get('nights'):
        doc.duration_nights = int(kwargs.get('duration_nights') or kwargs.get('nights'))
    if kwargs.get('visa_required') is not None:
        doc.visa_required = int(kwargs['visa_required'])
    if kwargs.get('description'):
        doc.description = kwargs['description']

    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return {'success': True, 'name': doc.name}

@frappe.whitelist()
def create_package(**kwargs):
    return save_package(**kwargs)

@frappe.whitelist()
def create_booking(**kwargs):
    if not frappe.db.table_exists('Booking'):
        return {'success': False, 'error': 'Booking table not found'}
    doc = frappe.get_doc({
        "doctype": "Booking",
        "customer": kwargs.get('customer',''),
        "customer_mobile": kwargs.get('customer_mobile') or kwargs.get('mobile',''),
        "tour_package": kwargs.get('tour_package',''),
        "departure_date": kwargs.get('departure_date') or kwargs.get('travel_date',''),
        "total_pax": int(kwargs.get('total_pax') or kwargs.get('pax_count') or 1),
        "sales_consultant": kwargs.get('sales_consultant',''),
        # booking.py will auto-calculate amounts from package pricing
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
    bname = kwargs.get('booking_name') or kwargs.get('booking_id')
    amount = float(kwargs.get('amount') or 0)
    if not bname or not amount:
        return {'success': False, 'error': 'Booking ID and amount required'}
    if frappe.db.exists('Booking', bname):
        return {'success': True, 'message': f'Payment of {amount} noted for {bname}'}
    return {'success': False, 'error': 'Booking not found'}

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
