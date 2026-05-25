import frappe


def get_context(context):
    context.no_cache = 1
    context.user = frappe.session.user
    context.is_guest = frappe.session.user == 'Guest'


@frappe.whitelist()
def get_portal_data():
    if frappe.session.user == 'Guest':
        frappe.throw("Please login", frappe.AuthenticationError)

    user = frappe.session.user

    # Find Travel Lead — try email first
    lead = frappe.db.get_value('Travel Lead',
        {'email_id': user},
        ['name','full_name','mobile_no','status','email_id',
         'suggested_package','preferred_month','pax_count',
         'assigned_consultant','interest_tags','remarks',
         'customer','converted_booking'],
        as_dict=True)

    # Fallback: match by mobile from User record
    if not lead:
        user_mobile = frappe.db.get_value('User', user, 'mobile_no') or ''
        if user_mobile:
            mobiles = [user_mobile,
                       user_mobile.replace('+91','').strip(),
                       '+91' + user_mobile.replace('+91','').strip()]
            lead = frappe.db.get_value('Travel Lead',
                {'mobile_no': ['in', mobiles]},
                ['name','full_name','mobile_no','status','email_id',
                 'suggested_package','preferred_month','pax_count',
                 'assigned_consultant','interest_tags','remarks',
                 'customer','converted_booking'],
                as_dict=True)

    if not lead:
        return {'lead': None, 'bookings': [], 'visas': [],
                'package_details': None, 'all_packages': [], 'all_destinations': []}

    # Enrich lead
    if lead.get('assigned_consultant'):
        lead['consultant_name'] = frappe.db.get_value(
            'User', lead['assigned_consultant'], 'full_name') or lead['assigned_consultant']
    else:
        lead['consultant_name'] = 'Not assigned'

    if lead.get('suggested_package'):
        lead['package_name'] = frappe.db.get_value(
            'Tour Package', lead['suggested_package'], 'package_name') or lead['suggested_package']
    else:
        lead['package_name'] = ''

    # ── Find bookings ──────────────────────────────────────────────────────
    # Strategy: search by customer link AND by mobile number
    booking_names = set()
    bookings_map = {}

    # 1. By customer link on lead
    customer = lead.get('customer')
    if customer:
        bks = frappe.get_all('Booking',
            filters={'customer': customer},
            fields=['name','customer','customer_mobile','tour_package',
                    'departure_date','total_pax','base_amount',
                    'gst_amount','tcs_amount','grand_total','creation'],
            order_by='creation desc')
        for b in bks:
            booking_names.add(b.name)
            bookings_map[b.name] = b

    # 2. By customer_mobile (covers bookings made without customer link)
    mobile = lead.get('mobile_no', '').strip()
    if mobile:
        mobiles = [mobile,
                   mobile.replace('+91','').strip(),
                   '+91' + mobile.replace('+91','').strip()]
        bks2 = frappe.get_all('Booking',
            filters={'customer_mobile': ['in', mobiles]},
            fields=['name','customer','customer_mobile','tour_package',
                    'departure_date','total_pax','base_amount',
                    'gst_amount','tcs_amount','grand_total','creation'],
            order_by='creation desc')
        for b in bks2:
            if b.name not in booking_names:
                booking_names.add(b.name)
                bookings_map[b.name] = b

    # 3. Also check customer linked via mobile (customer.mobile_no)
    if mobile and not customer:
        mobiles = [mobile, mobile.replace('+91','').strip()]
        cust_by_mobile = frappe.db.get_value('Customer',
            {'mobile_no': ['in', mobiles]}, 'name')
        if cust_by_mobile:
            bks3 = frappe.get_all('Booking',
                filters={'customer': cust_by_mobile},
                fields=['name','customer','customer_mobile','tour_package',
                        'departure_date','total_pax','base_amount',
                        'gst_amount','tcs_amount','grand_total','creation'],
                order_by='creation desc')
            for b in bks3:
                if b.name not in booking_names:
                    booking_names.add(b.name)
                    bookings_map[b.name] = b

    # Build final bookings list — enrich with package name
    bookings = sorted(bookings_map.values(),
                      key=lambda b: b.get('creation', ''), reverse=True)
    for b in bookings:
        if b.get('tour_package'):
            b['package_name'] = frappe.db.get_value(
                'Tour Package', b['tour_package'], 'package_name') or b['tour_package']
        else:
            b['package_name'] = '—'

    # ── Visa applications ──────────────────────────────────────────────────
    visas = []
    if booking_names:
        visas = frappe.get_all('Visa Application',
            filters={'booking': ['in', list(booking_names)]},
            fields=['name','booking','applicant_name','visa_type',
                    'destination_country','status','departure_date',
                    'submission_deadline','passport_number'],
            order_by='creation desc')

    # ── Package details ────────────────────────────────────────────────────
    package_details = None
    if lead.get('suggested_package'):
        try:
            pkg = frappe.get_doc('Tour Package', lead['suggested_package'])
            package_details = {
                'name': pkg.name,
                'package_name': pkg.package_name,
                'tour_type': pkg.tour_type,
                'destination': pkg.destination,
                'duration_days': pkg.duration_days,
                'duration_nights': pkg.duration_nights,
                'visa_required': pkg.visa_required,
            }
        except Exception:
            pass

    # ── All packages & destinations for dropdowns ──────────────────────────
    all_packages = frappe.get_all('Tour Package',
        fields=['name','package_name','tour_type','duration_days','duration_nights'],
        order_by='package_name asc', limit=100)

    all_destinations = frappe.get_all('Destination',
        fields=['name','destination_name'], limit=100)

    return {
        'lead': lead,
        'bookings': bookings,
        'visas': visas,
        'package_details': package_details,
        'all_packages': all_packages,
        'all_destinations': all_destinations,
        'customer': customer,
        'booking_count': len(bookings),
    }


@frappe.whitelist()
def update_lead_enquiry(**kwargs):
    if frappe.session.user == 'Guest':
        frappe.throw("Login required", frappe.AuthenticationError)

    lead_name = kwargs.get('lead_name')
    if not lead_name or not frappe.db.exists('Travel Lead', lead_name):
        return {'success': False, 'error': 'Lead not found'}

    owner_email = frappe.db.get_value('Travel Lead', lead_name, 'email_id')
    user_mobile = frappe.db.get_value('User', frappe.session.user, 'mobile_no') or ''
    lead_mobile = frappe.db.get_value('Travel Lead', lead_name, 'mobile_no') or ''

    is_owner = (owner_email == frappe.session.user or
                (user_mobile and lead_mobile and
                 user_mobile.replace('+91','') == lead_mobile.replace('+91','')))
    if not is_owner:
        return {'success': False, 'error': 'Unauthorized'}

    doc = frappe.get_doc('Travel Lead', lead_name)
    for f in ['full_name','mobile_no','pax_count','preferred_month',
              'suggested_package','remarks','interest_tags']:
        if kwargs.get(f) is not None:
            setattr(doc, f, kwargs[f])
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return {'success': True}


@frappe.whitelist()
def submit_new_enquiry(**kwargs):
    if frappe.session.user == 'Guest':
        frappe.throw("Login required", frappe.AuthenticationError)

    user = frappe.session.user
    existing = frappe.db.get_value('Travel Lead', {'email_id': user}, 'name')

    if existing:
        doc = frappe.get_doc('Travel Lead', existing)
        if kwargs.get('suggested_package'): doc.suggested_package = kwargs['suggested_package']
        if kwargs.get('preferred_month'): doc.preferred_month = kwargs['preferred_month']
        if kwargs.get('pax_count'): doc.pax_count = int(kwargs['pax_count'])
        if kwargs.get('remarks'):
            doc.remarks = ((doc.remarks or '') + '\n\nNew Enquiry: ' + kwargs['remarks']).strip()
        if kwargs.get('interest_tags'): doc.interest_tags = kwargs['interest_tags']
        doc.save(ignore_permissions=True)
        frappe.db.commit()
        return {'success': True, 'name': doc.name, 'action': 'updated'}
    else:
        user_name = frappe.db.get_value('User', user, 'full_name') or user
        user_mobile = frappe.db.get_value('User', user, 'mobile_no') or ''
        doc = frappe.get_doc({
            'doctype': 'Travel Lead',
            'full_name': user_name,
            'email_id': user,
            'mobile_no': user_mobile,
            'status': 'Open',
            'source': 'Website',
            'suggested_package': kwargs.get('suggested_package', ''),
            'preferred_month': kwargs.get('preferred_month', ''),
            'pax_count': int(kwargs.get('pax_count') or 1),
            'remarks': kwargs.get('remarks', ''),
            'interest_tags': kwargs.get('interest_tags', ''),
        })
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
        return {'success': True, 'name': doc.name, 'action': 'created'}


@frappe.whitelist(allow_guest=True)
def portal_login(**kwargs):
    mobile = (kwargs.get('mobile') or '').strip()
    password = (kwargs.get('password') or '').strip()
    if not mobile or not password:
        return {'success': False, 'error': 'Mobile and password required'}
    try:
        lead = frappe.db.get_value('Travel Lead',
            {'mobile_no': mobile}, ['name','email_id','full_name'], as_dict=True)
        if not lead or not lead.email_id:
            return {'success': False, 'error': 'Account not found for this mobile number'}
        from frappe.auth import LoginManager
        lm = LoginManager()
        lm.authenticate(user=lead.email_id, pwd=password)
        lm.post_login()
        return {'success': True, 'redirect': '/travel_enquiry', 'full_name': lead.full_name}
    except frappe.AuthenticationError:
        return {'success': False, 'error': 'Invalid credentials'}
    except Exception as e:
        return {'success': False, 'error': str(e)}
