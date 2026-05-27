import frappe


def get_context(context):
    context.no_cache = 1
    context.user = frappe.session.user
    context.is_guest = frappe.session.user == 'Guest'


@frappe.whitelist()
def get_portal_data():
    """Get all data for the logged-in customer's portal."""
    if frappe.session.user == 'Guest':
        frappe.throw("Please login", frappe.AuthenticationError)

    user = frappe.session.user

    # Find Travel Lead by email
    lead = frappe.db.get_value('Travel Lead',
        {'email_id': user},
        ['name','full_name','mobile_no','status','email_id',
         'suggested_package','preferred_month','pax_count',
         'assigned_consultant','interest_tags','remarks',
         'customer','converted_booking'],
        as_dict=True)

    # Fallback: match by mobile from User record
    if not lead:
        mobile = frappe.db.get_value('User', user, 'mobile_no') or ''
        if mobile:
            mobile_clean = mobile.replace('+91','').replace(' ','').strip()
            lead = frappe.db.get_value('Travel Lead',
                {'mobile_no': ['in', [mobile, mobile_clean, '+91'+mobile_clean]]},
                ['name','full_name','mobile_no','status','email_id',
                 'suggested_package','preferred_month','pax_count',
                 'assigned_consultant','interest_tags','remarks',
                 'customer','converted_booking'],
                as_dict=True)

    if not lead:
        return {'lead': None, 'bookings': [], 'visas': [], 'package_details': None}

    # Enrich lead with consultant name
    if lead.get('assigned_consultant'):
        cn = frappe.db.get_value('User', lead['assigned_consultant'], 'full_name')
        lead['consultant_name'] = cn or lead['assigned_consultant']
    else:
        lead['consultant_name'] = 'Not assigned'

    # Enrich with package name
    if lead.get('suggested_package'):
        pn = frappe.db.get_value('Tour Package', lead['suggested_package'], 'package_name')
        lead['package_name'] = pn or lead['suggested_package']
    else:
        lead['package_name'] = ''

    # Bookings linked to customer
    bookings = []
    customer = lead.get('customer')
    if not customer and lead.get('mobile_no'):
        customer = frappe.db.get_value('Customer',
            {'mobile_no': lead['mobile_no']}, 'name')
    if customer:
        bookings = frappe.get_all('Booking',
            filters={'customer': customer},
            fields=['name','tour_package','departure_date','total_pax',
                    'base_amount','gst_amount','tcs_amount','grand_total','creation'],
            order_by='creation desc')
        # Enrich with package name
        for b in bookings:
            if b.get('tour_package'):
                pn = frappe.db.get_value('Tour Package', b['tour_package'], 'package_name')
                b['package_name'] = pn or b['tour_package']

    # Visa applications
    visas = []
    if bookings:
        bk_names = [b.name for b in bookings]
        visas = frappe.get_all('Visa Application',
            filters={'booking': ['in', bk_names]},
            fields=['name','booking','applicant_name','visa_type',
                    'destination_country','status','departure_date',
                    'submission_deadline','passport_number'],
            order_by='creation desc')

    # Package details for suggested package
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
                'description': (pkg.description or '').replace('<[^>]*>', ''),
            }
        except Exception:
            pass

    # All available packages for new enquiry
    all_packages = frappe.get_all('Tour Package',
        fields=['name','package_name','tour_type','duration_days','duration_nights'],
        order_by='package_name asc', limit=50)

    # All destinations
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
    }


@frappe.whitelist()
def update_lead_enquiry(**kwargs):
    """Customer updates their own enquiry/profile."""
    if frappe.session.user == 'Guest':
        frappe.throw("Login required", frappe.AuthenticationError)

    lead_name = kwargs.get('lead_name')
    if not lead_name or not frappe.db.exists('Travel Lead', lead_name):
        return {'success': False, 'error': 'Lead not found'}

    # Security: verify this lead belongs to current user
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
    """Customer submits a new travel enquiry — creates/updates Travel Lead."""
    if frappe.session.user == 'Guest':
        frappe.throw("Login required", frappe.AuthenticationError)

    user = frappe.session.user

    # Check if lead already exists
    existing = frappe.db.get_value('Travel Lead', {'email_id': user}, 'name')

    if existing:
        doc = frappe.get_doc('Travel Lead', existing)
        # Update with new enquiry details
        if kwargs.get('suggested_package'):
            doc.suggested_package = kwargs['suggested_package']
        if kwargs.get('preferred_month'):
            doc.preferred_month = kwargs['preferred_month']
        if kwargs.get('pax_count'):
            doc.pax_count = int(kwargs['pax_count'])
        if kwargs.get('remarks'):
            existing_remarks = doc.remarks or ''
            new_remark = kwargs.get('remarks', '')
            doc.remarks = (existing_remarks + '\n\nNew Enquiry: ' + new_remark).strip()
        if kwargs.get('interest_tags'):
            doc.interest_tags = kwargs['interest_tags']
        doc.save(ignore_permissions=True)
        frappe.db.commit()
        return {'success': True, 'name': doc.name, 'action': 'updated'}
    else:
        # Create new lead
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
