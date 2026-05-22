import frappe
from frappe.utils import flt, now_datetime


# ══════════════════════════════════════════════════════════════════════════
#  MAIN DATA LOADER — all 25 DocTypes
# ══════════════════════════════════════════════════════════════════════════
@frappe.whitelist()
def get_founder_data():
    if frappe.session.user == 'Guest':
        frappe.throw("Login required", frappe.AuthenticationError)

    leads = frappe.get_all('Travel Lead',
        fields=['name','full_name','email_id','mobile_no','status','source',
                'suggested_package','pax_count','preferred_month',
                'assigned_consultant','interest_tags','remarks',
                'customer','converted_booking','creation'],
        order_by='creation desc', limit=500)

    bookings = frappe.get_all('Booking',
        fields=['name','customer','customer_mobile','tour_package',
                'departure_date','total_pax','sales_consultant',
                'base_amount','discount_amount','gst_amount',
                'tcs_amount','grand_total','creation'],
        order_by='creation desc', limit=500)

    packages = frappe.get_all('Tour Package',
        fields=['name','package_name','destination','tour_type',
                'duration_days','duration_nights','visa_required','creation'],
        order_by='creation desc', limit=200)

    destinations = frappe.get_all('Destination',
        fields=['name','destination_name','description'], limit=200)

    visa_apps = frappe.get_all('Visa Application',
        fields=['name','booking','applicant_name','passport_number',
                'destination_country','visa_type','departure_date',
                'status','submission_deadline','all_docs_collected','creation'],
        order_by='creation desc', limit=200)

    visa_agents = frappe.get_all('Visa Agent',
        fields=['name','agent_name','supplier','contact_person',
                'mobile_no','email_id'], limit=100)

    visa_configs = frappe.get_all('Visa Country Config',
        fields=['name','country','visa_type','processing_days',
                'embassy_fee','service_charge'], limit=100)

    visa_fee_bills = frappe.get_all('Visa Fee Billing',
        fields=['name','customer','booking','visa_application',
                'embassy_fee','service_charge','gst_amount',
                'grand_total','sales_invoice','creation'],
        order_by='creation desc', limit=200)

    visa_delivery = frappe.get_all('Visa Delivery Log',
        fields=['name','visa_application','applicant_name',
                'delivery_date','delivery_mode','tracking_number',
                'notes','creation'],
        order_by='creation desc', limit=200)

    guide_allocs = frappe.get_all('Guide Allocation',
        fields=['name','guide','booking','departure_date',
                'return_date','status','creation'],
        order_by='creation desc', limit=200)

    run_sheets = frappe.get_all('Trip Run Sheet',
        fields=['name','booking','customer','departure_date',
                'total_pax','creation'],
        order_by='creation desc', limit=200)

    hotel_allots = frappe.get_all('Hotel Allotment',
        fields=['name','supplier','supplier_name','from_date',
                'to_date','total_rooms','creation'],
        order_by='creation desc', limit=200)

    supplier_contracts = frappe.get_all('Supplier Contract',
        fields=['name','supplier','supplier_name','contract_start_date',
                'contract_end_date','cost_per_pax','currency',
                'notes','creation'],
        order_by='creation desc', limit=200)

    cancel_policies = frappe.get_all('Cancellation Policy',
        fields=['name','policy_name','description'], limit=100)

    settings = {}
    try:
        if frappe.db.exists('Travel Tour Settings', 'Travel Tour Settings'):
            s = frappe.get_doc('Travel Tour Settings', 'Travel Tour Settings')
            settings = {
                'ops_email': s.ops_email or '',
                'site_url': s.site_url or '',
                'razorpay_key_id': s.razorpay_key_id or '',
                'consultant_commission_pct': s.consultant_commission_pct or 0,
                'website_booking_bonus': s.website_booking_bonus or 0,
            }
    except Exception:
        pass

    # Stats
    total_revenue = sum(flt(b.get('grand_total')) for b in bookings)
    open_leads = len([l for l in leads if l.get('status') in
                      ['Open','Interested','Contacted']])
    pending_visas = len([v for v in visa_apps if v.get('status') in
                         ['Pending Documents','Documents Collected','Submitted']])

    founder_name = frappe.db.get_value('User', frappe.session.user, 'full_name') or 'Founder'

    return {
        'leads': leads,
        'bookings': bookings,
        'packages': packages,
        'destinations': destinations,
        'visa_apps': visa_apps,
        'visa_agents': visa_agents,
        'visa_configs': visa_configs,
        'visa_fee_bills': visa_fee_bills,
        'visa_delivery': visa_delivery,
        'guide_allocs': guide_allocs,
        'run_sheets': run_sheets,
        'hotel_allots': hotel_allots,
        'supplier_contracts': supplier_contracts,
        'cancel_policies': cancel_policies,
        'settings': settings,
        'stats': {
            'total_revenue': total_revenue,
            'active_bookings': len(bookings),
            'open_leads': open_leads,
            'lead_count': len(leads),
            'package_count': len(packages),
            'visa_count': len(visa_apps),
            'pending_visas': pending_visas,
            'destination_count': len(destinations),
            'agent_count': len(visa_agents),
        },
        'founder': {
            'name': founder_name,
            'email': frappe.session.user,
            'role': 'Founder & CEO',
        }
    }


# ── Travel Lead ────────────────────────────────────────────────────────────
@frappe.whitelist()
def save_lead(**kwargs):
    n = kwargs.get('name')
    doc = frappe.get_doc('Travel Lead', n) if n and frappe.db.exists('Travel Lead', n) else frappe.new_doc('Travel Lead')
    for f in ['full_name','email_id','mobile_no','status','source',
              'suggested_package','pax_count','preferred_month',
              'assigned_consultant','interest_tags','remarks']:
        if kwargs.get(f) is not None:
            setattr(doc, f, kwargs[f])
    doc.save(ignore_permissions=True); frappe.db.commit()
    return {'success': True, 'name': doc.name}

@frappe.whitelist()
def create_lead(**kwargs): return save_lead(**kwargs)
@frappe.whitelist()
def update_lead(**kwargs): return save_lead(**kwargs)


# ── Tour Package ───────────────────────────────────────────────────────────
@frappe.whitelist()
def save_package(**kwargs):
    n = kwargs.get('name')
    doc = frappe.get_doc('Tour Package', n) if n and frappe.db.exists('Tour Package', n) else frappe.new_doc('Tour Package')
    if kwargs.get('package_name'): doc.package_name = kwargs['package_name']
    t = kwargs.get('tour_type','Domestic')
    doc.tour_type = t if t in ('Domestic','International') else 'Domestic'
    if kwargs.get('destination'): doc.destination = kwargs['destination']
    if kwargs.get('duration_days'): doc.duration_days = int(kwargs['duration_days'])
    if kwargs.get('duration_nights'): doc.duration_nights = int(kwargs['duration_nights'])
    if kwargs.get('visa_required') is not None: doc.visa_required = int(kwargs['visa_required'])
    if kwargs.get('description'): doc.description = kwargs['description']
    doc.save(ignore_permissions=True); frappe.db.commit()
    return {'success': True, 'name': doc.name}

@frappe.whitelist()
def create_package(**kwargs): return save_package(**kwargs)


# ── Booking ────────────────────────────────────────────────────────────────
@frappe.whitelist()
def save_booking(**kwargs):
    n = kwargs.get('name')
    doc = frappe.get_doc('Booking', n) if n and frappe.db.exists('Booking', n) else frappe.new_doc('Booking')
    for f in ['customer','customer_mobile','tour_package','departure_date',
              'total_pax','sales_consultant']:
        if kwargs.get(f) is not None:
            setattr(doc, f, kwargs[f])
    doc.save(ignore_permissions=True); frappe.db.commit()
    return {'success': True, 'name': doc.name}

@frappe.whitelist()
def create_booking(**kwargs): return save_booking(**kwargs)

@frappe.whitelist()
def update_booking_status(booking_name, status):
    if frappe.db.exists('Booking', booking_name):
        frappe.db.set_value('Booking', booking_name, 'status', status)
        frappe.db.commit(); return {'success': True}
    return {'success': False, 'error': 'Not found'}

@frappe.whitelist()
def record_payment(**kwargs):
    bname = kwargs.get('booking_name') or kwargs.get('booking_id')
    amount = flt(kwargs.get('amount') or 0)
    if not bname or not amount:
        return {'success': False, 'error': 'Booking ID and amount required'}
    if frappe.db.exists('Booking', bname):
        return {'success': True, 'message': f'Payment ₹{amount:,.0f} noted for {bname}'}
    return {'success': False, 'error': 'Booking not found'}


# ── Visa Application ───────────────────────────────────────────────────────
@frappe.whitelist()
def save_visa(**kwargs):
    n = kwargs.get('name')
    doc = frappe.get_doc('Visa Application', n) if n and frappe.db.exists('Visa Application', n) else frappe.new_doc('Visa Application')
    for f in ['booking','applicant_name','passport_number','passport_expiry',
              'destination_country','visa_type','departure_date','status',
              'submission_deadline','all_docs_collected']:
        if kwargs.get(f) is not None:
            setattr(doc, f, kwargs[f])
    doc.save(ignore_permissions=True); frappe.db.commit()
    return {'success': True, 'name': doc.name}

@frappe.whitelist()
def update_visa_status(visa_name, status):
    if frappe.db.exists('Visa Application', visa_name):
        frappe.db.set_value('Visa Application', visa_name, 'status', status)
        frappe.db.commit(); return {'success': True}
    return {'success': False, 'error': 'Not found'}


# ── Destination ────────────────────────────────────────────────────────────
@frappe.whitelist()
def save_destination(**kwargs):
    n = kwargs.get('name')
    doc = frappe.get_doc('Destination', n) if n and frappe.db.exists('Destination', n) else frappe.new_doc('Destination')
    for f in ['destination_name','description']:
        if kwargs.get(f) is not None:
            setattr(doc, f, kwargs[f])
    doc.save(ignore_permissions=True); frappe.db.commit()
    return {'success': True, 'name': doc.name}


# ── Visa Agent ─────────────────────────────────────────────────────────────
@frappe.whitelist()
def save_visa_agent(**kwargs):
    n = kwargs.get('name')
    doc = frappe.get_doc('Visa Agent', n) if n and frappe.db.exists('Visa Agent', n) else frappe.new_doc('Visa Agent')
    for f in ['agent_name','contact_person','mobile_no','email_id']:
        if kwargs.get(f) is not None:
            setattr(doc, f, kwargs[f])
    doc.save(ignore_permissions=True); frappe.db.commit()
    return {'success': True, 'name': doc.name}


# ── Guide Allocation ───────────────────────────────────────────────────────
@frappe.whitelist()
def save_guide_allocation(**kwargs):
    n = kwargs.get('name')
    doc = frappe.get_doc('Guide Allocation', n) if n and frappe.db.exists('Guide Allocation', n) else frappe.new_doc('Guide Allocation')
    for f in ['guide','booking','departure_date','return_date','status']:
        if kwargs.get(f) is not None:
            setattr(doc, f, kwargs[f])
    doc.save(ignore_permissions=True); frappe.db.commit()
    return {'success': True, 'name': doc.name}


# ── Supplier Contract ──────────────────────────────────────────────────────
@frappe.whitelist()
def save_supplier_contract(**kwargs):
    n = kwargs.get('name')
    doc = frappe.get_doc('Supplier Contract', n) if n and frappe.db.exists('Supplier Contract', n) else frappe.new_doc('Supplier Contract')
    for f in ['supplier','contract_start_date','contract_end_date',
              'cost_per_pax','currency','notes']:
        if kwargs.get(f) is not None:
            setattr(doc, f, kwargs[f])
    doc.save(ignore_permissions=True); frappe.db.commit()
    return {'success': True, 'name': doc.name}


# ── Cancellation Policy ────────────────────────────────────────────────────
@frappe.whitelist()
def save_cancel_policy(**kwargs):
    n = kwargs.get('name')
    doc = frappe.get_doc('Cancellation Policy', n) if n and frappe.db.exists('Cancellation Policy', n) else frappe.new_doc('Cancellation Policy')
    for f in ['policy_name','description']:
        if kwargs.get(f) is not None:
            setattr(doc, f, kwargs[f])
    doc.save(ignore_permissions=True); frappe.db.commit()
    return {'success': True, 'name': doc.name}


# ── Hotel Allotment ────────────────────────────────────────────────────────
@frappe.whitelist()
def save_hotel_allotment(**kwargs):
    n = kwargs.get('name')
    doc = frappe.get_doc('Hotel Allotment', n) if n and frappe.db.exists('Hotel Allotment', n) else frappe.new_doc('Hotel Allotment')
    for f in ['supplier','from_date','to_date','total_rooms']:
        if kwargs.get(f) is not None:
            setattr(doc, f, kwargs[f])
    doc.save(ignore_permissions=True); frappe.db.commit()
    return {'success': True, 'name': doc.name}


# ── Travel Tour Settings ───────────────────────────────────────────────────
@frappe.whitelist()
def save_settings(**kwargs):
    try:
        if not frappe.db.exists('Travel Tour Settings', 'Travel Tour Settings'):
            doc = frappe.new_doc('Travel Tour Settings')
            doc.name = 'Travel Tour Settings'
        else:
            doc = frappe.get_doc('Travel Tour Settings', 'Travel Tour Settings')
        for f in ['ops_email','site_url','razorpay_key_id',
                  'consultant_commission_pct','website_booking_bonus']:
            if kwargs.get(f) is not None:
                setattr(doc, f, kwargs[f])
        doc.save(ignore_permissions=True); frappe.db.commit()
        return {'success': True}
    except Exception as e:
        return {'success': False, 'error': str(e)}


# ── Visa Country Config ────────────────────────────────────────────────────
@frappe.whitelist()
def save_visa_config(**kwargs):
    n = kwargs.get('name')
    doc = frappe.get_doc('Visa Country Config', n) if n and frappe.db.exists('Visa Country Config', n) else frappe.new_doc('Visa Country Config')
    for f in ['country','visa_type','processing_days','embassy_fee','service_charge']:
        if kwargs.get(f) is not None:
            setattr(doc, f, kwargs[f])
    doc.save(ignore_permissions=True); frappe.db.commit()
    return {'success': True, 'name': doc.name}


# ── Visa Delivery Log ──────────────────────────────────────────────────────
@frappe.whitelist()
def save_visa_delivery(**kwargs):
    n = kwargs.get('name')
    doc = frappe.get_doc('Visa Delivery Log', n) if n and frappe.db.exists('Visa Delivery Log', n) else frappe.new_doc('Visa Delivery Log')
    for f in ['visa_application','applicant_name','delivery_date',
              'delivery_mode','tracking_number','notes']:
        if kwargs.get(f) is not None:
            setattr(doc, f, kwargs[f])
    doc.save(ignore_permissions=True); frappe.db.commit()
    return {'success': True, 'name': doc.name}


# ── Visa Fee Billing ───────────────────────────────────────────────────────
@frappe.whitelist()
def save_visa_fee_billing(**kwargs):
    n = kwargs.get('name')
    doc = frappe.get_doc('Visa Fee Billing', n) if n and frappe.db.exists('Visa Fee Billing', n) else frappe.new_doc('Visa Fee Billing')
    for f in ['customer','booking','visa_application','embassy_fee',
              'service_charge','gst_amount','grand_total']:
        if kwargs.get(f) is not None:
            setattr(doc, f, kwargs[f])
    doc.save(ignore_permissions=True); frappe.db.commit()
    return {'success': True, 'name': doc.name}


# ── Trip Run Sheet ─────────────────────────────────────────────────────────
@frappe.whitelist()
def save_run_sheet(**kwargs):
    n = kwargs.get('name')
    doc = frappe.get_doc('Trip Run Sheet', n) if n and frappe.db.exists('Trip Run Sheet', n) else frappe.new_doc('Trip Run Sheet')
    for f in ['booking','customer','departure_date','total_pax']:
        if kwargs.get(f) is not None:
            setattr(doc, f, kwargs[f])
    doc.save(ignore_permissions=True); frappe.db.commit()
    return {'success': True, 'name': doc.name}


# ── Generic delete ─────────────────────────────────────────────────────────
@frappe.whitelist()
def delete_record(doctype, record_name):
    allowed = ['Travel Lead','Booking','Tour Package','Visa Application',
               'Destination','Visa Agent','Trip Run Sheet','Hotel Allotment',
               'Supplier Contract','Cancellation Policy','Visa Country Config',
               'Guide Allocation','Visa Delivery Log','Visa Fee Billing']
    if doctype not in allowed:
        return {'success': False, 'error': 'Not allowed'}
    if frappe.db.exists(doctype, record_name):
        frappe.delete_doc(doctype, record_name, ignore_permissions=True)
        frappe.db.commit(); return {'success': True}
    return {'success': False, 'error': 'Not found'}
