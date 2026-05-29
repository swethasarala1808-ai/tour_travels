import frappe
from frappe.utils import flt, now_datetime


# ══════════════════════════════════════════════════════════════════════════
#  CSRF TOKEN — fetch for frontend use
# ══════════════════════════════════════════════════════════════════════════
@frappe.whitelist()
def get_csrf_token():
    """Return the current session CSRF token for use in frontend API calls."""
    return frappe.session.data.csrf_token if frappe.session.data else ''


# ══════════════════════════════════════════════════════════════════════════
#  MAIN DATA LOADER
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
                'status','submission_deadline','creation'],
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
                'grand_total','creation'],
        order_by='creation desc', limit=200)

    visa_delivery = frappe.get_all('Visa Delivery Log',
        fields=['name','visa_application','applicant_name',
                'delivery_date','delivery_mode','tracking_number','creation'],
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
                'contract_end_date','cost_per_pax','notes','creation'],
        order_by='creation desc', limit=200)

    cancel_policies = frappe.get_all('Cancellation Policy',
        fields=['name','policy_name','description'], limit=100)

    users = frappe.get_all('User',
        filters={'enabled': 1, 'user_type': 'System User'},
        fields=['name','full_name'], limit=100)

    customers = frappe.get_all('Customer',
        fields=['name','customer_name'], limit=200)

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

    # Include session CSRF token so JS can use it
    csrf = frappe.session.data.csrf_token if frappe.session.data else ''

    total_revenue = sum(flt(b.get('grand_total')) for b in bookings)
    open_leads = len([l for l in leads if l.get('status') in ['Open','Interested']])
    pending_visas = len([v for v in visa_apps if v.get('status') not in ['Approved','Delivered']])
    founder_name = frappe.db.get_value('User', frappe.session.user, 'full_name') or 'Founder'

    return {
        'leads': leads, 'bookings': bookings, 'packages': packages,
        'destinations': destinations, 'visa_apps': visa_apps,
        'visa_agents': visa_agents, 'visa_configs': visa_configs,
        'visa_fee_bills': visa_fee_bills, 'visa_delivery': visa_delivery,
        'guide_allocs': guide_allocs, 'run_sheets': run_sheets,
        'hotel_allots': hotel_allots, 'supplier_contracts': supplier_contracts,
        'cancel_policies': cancel_policies, 'settings': settings,
        'users': users, 'customers': customers,
        'csrf_token': csrf,
        'stats': {
            'total_revenue': total_revenue,
            'active_bookings': len(bookings),
            'open_leads': open_leads,
            'lead_count': len(leads),
            'package_count': len(packages),
            'visa_count': len(visa_apps),
            'pending_visas': pending_visas,
            'destination_count': len(destinations),
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
    doc.save(ignore_permissions=True)
    frappe.db.commit()
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
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return {'success': True, 'name': doc.name}

@frappe.whitelist()
def create_package(**kwargs): return save_package(**kwargs)


# ── Booking — auto-create customer from mobile ─────────────────────────────
@frappe.whitelist()
def save_booking(**kwargs):
    n = kwargs.get('name')
    doc = frappe.get_doc('Booking', n) if n and frappe.db.exists('Booking', n) else frappe.new_doc('Booking')

    # customer is mandatory Link[Customer] — resolve or create
    customer = kwargs.get('customer', '')
    mobile = kwargs.get('customer_mobile', '')

    if not customer and mobile:
        # Try to find existing customer by mobile
        cust = frappe.db.get_value('Customer', {'mobile_no': mobile}, 'name')
        if not cust:
            # Try via lead
            lead = frappe.db.get_value('Travel Lead', {'mobile_no': mobile}, 'customer')
            if lead:
                cust = lead
        if not cust:
            # Create a new customer
            try:
                cust_doc = frappe.get_doc({
                    'doctype': 'Customer',
                    'customer_name': f'Customer {mobile}',
                    'customer_type': 'Individual',
                    'customer_group': frappe.db.get_value('Customer Group',
                        {'is_group': 0}, 'name') or 'Individual',
                    'territory': frappe.db.get_value('Territory',
                        {'is_group': 0}, 'name') or 'All Territories',
                    'mobile_no': mobile,
                })
                cust_doc.insert(ignore_permissions=True)
                frappe.db.commit()
                cust = cust_doc.name
            except Exception as e:
                frappe.log_error(f"Customer create failed: {e}")
        customer = cust or ''

    if customer: doc.customer = customer
    if mobile: doc.customer_mobile = mobile
    if kwargs.get('tour_package'): doc.tour_package = kwargs['tour_package']
    if kwargs.get('departure_date'): doc.departure_date = kwargs['departure_date']
    if kwargs.get('total_pax'): doc.total_pax = int(kwargs['total_pax'])

    # sales_consultant is Link[User]
    sc = kwargs.get('sales_consultant', '')
    if sc and frappe.db.exists('User', sc):
        doc.sales_consultant = sc

    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return {'success': True, 'name': doc.name}

@frappe.whitelist()
def create_booking(**kwargs): return save_booking(**kwargs)

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
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return {'success': True, 'name': doc.name}

@frappe.whitelist()
def update_visa_status(visa_name, status):
    if frappe.db.exists('Visa Application', visa_name):
        frappe.db.set_value('Visa Application', visa_name, 'status', status)
        frappe.db.commit()
        return {'success': True}
    return {'success': False, 'error': 'Not found'}


# ── Destination ────────────────────────────────────────────────────────────
@frappe.whitelist()
def save_destination(**kwargs):
    n = kwargs.get('name')
    doc = frappe.get_doc('Destination', n) if n and frappe.db.exists('Destination', n) else frappe.new_doc('Destination')
    for f in ['destination_name','description']:
        if kwargs.get(f) is not None:
            setattr(doc, f, kwargs[f])
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return {'success': True, 'name': doc.name}


# ── Visa Agent ─────────────────────────────────────────────────────────────
@frappe.whitelist()
def save_visa_agent(**kwargs):
    n = kwargs.get('name')
    doc = frappe.get_doc('Visa Agent', n) if n and frappe.db.exists('Visa Agent', n) else frappe.new_doc('Visa Agent')
    for f in ['agent_name','contact_person','mobile_no','email_id']:
        if kwargs.get(f) is not None:
            setattr(doc, f, kwargs[f])
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return {'success': True, 'name': doc.name}


# ── Guide Allocation ───────────────────────────────────────────────────────
@frappe.whitelist()
def save_guide_allocation(**kwargs):
    n = kwargs.get('name')
    doc = frappe.get_doc('Guide Allocation', n) if n and frappe.db.exists('Guide Allocation', n) else frappe.new_doc('Guide Allocation')
    for f in ['guide','booking','departure_date','return_date','status']:
        if kwargs.get(f) is not None:
            setattr(doc, f, kwargs[f])
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return {'success': True, 'name': doc.name}


# ── Supplier Contract ──────────────────────────────────────────────────────
@frappe.whitelist()
def save_supplier_contract(**kwargs):
    n = kwargs.get('name')
    doc = frappe.get_doc('Supplier Contract', n) if n and frappe.db.exists('Supplier Contract', n) else frappe.new_doc('Supplier Contract')
    # supplier is Link[Supplier] — resolve or create
    supplier_input = kwargs.get('supplier', '')
    if supplier_input:
        if frappe.db.exists('Supplier', supplier_input):
            doc.supplier = supplier_input
        else:
            # Try by name
            s = frappe.db.get_value('Supplier', {'supplier_name': supplier_input}, 'name')
            if s:
                doc.supplier = s
            else:
                try:
                    sg = frappe.db.get_value('Supplier Group', {'is_group': 0}, 'name') or 'All Supplier Groups'
                    sup = frappe.get_doc({'doctype':'Supplier','supplier_name':supplier_input,'supplier_group':sg})
                    sup.insert(ignore_permissions=True)
                    frappe.db.commit()
                    doc.supplier = sup.name
                except Exception:
                    pass

    for f in ['contract_start_date','contract_end_date','cost_per_pax','notes']:
        if kwargs.get(f) is not None:
            setattr(doc, f, kwargs[f])
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return {'success': True, 'name': doc.name}


# ── Cancellation Policy ────────────────────────────────────────────────────
@frappe.whitelist()
def save_cancel_policy(**kwargs):
    n = kwargs.get('name')
    doc = frappe.get_doc('Cancellation Policy', n) if n and frappe.db.exists('Cancellation Policy', n) else frappe.new_doc('Cancellation Policy')
    for f in ['policy_name','description']:
        if kwargs.get(f) is not None:
            setattr(doc, f, kwargs[f])
    # Always add/update a slab
    days = int(kwargs.get('slab_days') or 30)
    pct = float(kwargs.get('slab_pct') or 25)
    if not doc.slabs:
        doc.append('slabs', {'days_before_departure': days, 'cancellation_fee_percent': pct})
    else:
        doc.slabs[0].days_before_departure = days
        doc.slabs[0].cancellation_fee_percent = pct
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return {'success': True, 'name': doc.name}


# ── Hotel Allotment — auto-create item for room type ──────────────────────
@frappe.whitelist()
def save_hotel_allotment(**kwargs):
    n = kwargs.get('name')
    doc = frappe.get_doc('Hotel Allotment', n) if n and frappe.db.exists('Hotel Allotment', n) else frappe.new_doc('Hotel Allotment')

    # Supplier
    supplier_input = kwargs.get('supplier', '')
    if supplier_input:
        if frappe.db.exists('Supplier', supplier_input):
            doc.supplier = supplier_input
        else:
            s = frappe.db.get_value('Supplier', {'supplier_name': supplier_input}, 'name')
            if s:
                doc.supplier = s
            else:
                try:
                    sg = frappe.db.get_value('Supplier Group', {'is_group': 0}, 'name') or 'All Supplier Groups'
                    sup = frappe.get_doc({'doctype':'Supplier','supplier_name':supplier_input,'supplier_group':sg})
                    sup.insert(ignore_permissions=True)
                    frappe.db.commit()
                    doc.supplier = sup.name
                except Exception:
                    pass

    if kwargs.get('from_date'): doc.from_date = kwargs['from_date']
    if kwargs.get('to_date'): doc.to_date = kwargs['to_date']
    if kwargs.get('total_rooms'): doc.total_rooms = int(kwargs['total_rooms'])

    # rooms table is mandatory — auto-create Item for room type
    room_type_name = kwargs.get('room_type', '').strip() or 'Standard Room'
    qty = int(kwargs.get('room_qty') or kwargs.get('total_rooms') or 1)

    # Find or create the Item
    if not frappe.db.exists('Item', room_type_name):
        try:
            ig = frappe.db.get_value('Item Group', {'is_group': 0}, 'name') or 'All Item Groups'
            item = frappe.get_doc({
                'doctype': 'Item', 'item_code': room_type_name,
                'item_name': room_type_name, 'item_group': ig,
                'is_stock_item': 0,
            })
            item.insert(ignore_permissions=True)
            frappe.db.commit()
        except Exception:
            # Use any existing item
            existing = frappe.get_all('Item', filters={'is_stock_item': 0}, pluck='name', limit=1)
            if existing:
                room_type_name = existing[0]

    # Set rooms table
    if not doc.rooms:
        doc.append('rooms', {'room_type': room_type_name, 'quantity': qty})
    else:
        doc.rooms[0].room_type = room_type_name
        doc.rooms[0].quantity = qty

    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return {'success': True, 'name': doc.name}


# ── Visa Fee Billing ───────────────────────────────────────────────────────
@frappe.whitelist()
def save_visa_fee_billing(**kwargs):
    n = kwargs.get('name')
    doc = frappe.get_doc('Visa Fee Billing', n) if n and frappe.db.exists('Visa Fee Billing', n) else frappe.new_doc('Visa Fee Billing')

    # customer is mandatory
    customer = kwargs.get('customer', '')
    if not customer and kwargs.get('booking'):
        customer = frappe.db.get_value('Booking', kwargs['booking'], 'customer') or ''
    if customer and frappe.db.exists('Customer', customer):
        doc.customer = customer

    if kwargs.get('booking'): doc.booking = kwargs['booking']
    if kwargs.get('visa_application'): doc.visa_application = kwargs['visa_application']
    doc.embassy_fee = flt(kwargs.get('embassy_fee') or 0)
    doc.service_charge = flt(kwargs.get('service_charge') or 0)
    doc.grand_total = doc.embassy_fee + doc.service_charge
    doc.save(ignore_permissions=True)
    frappe.db.commit()
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
        doc.save(ignore_permissions=True)
        frappe.db.commit()
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
    doc.save(ignore_permissions=True)
    frappe.db.commit()
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
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return {'success': True, 'name': doc.name}


# ── Trip Run Sheet ─────────────────────────────────────────────────────────
@frappe.whitelist()
def save_run_sheet(**kwargs):
    n = kwargs.get('name')
    doc = frappe.get_doc('Trip Run Sheet', n) if n and frappe.db.exists('Trip Run Sheet', n) else frappe.new_doc('Trip Run Sheet')
    for f in ['booking','customer','departure_date','total_pax']:
        if kwargs.get(f) is not None:
            setattr(doc, f, kwargs[f])
    doc.save(ignore_permissions=True)
    frappe.db.commit()
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
        frappe.db.commit()
        return {'success': True}
    return {'success': False, 'error': 'Not found'}
