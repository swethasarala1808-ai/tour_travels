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

    # Find Travel Lead linked to this user's email
    lead = frappe.db.get_value('Travel Lead',
        {'email_id': user},
        ['name','full_name','mobile_no','status','email_id',
         'suggested_package','preferred_month','pax_count',
         'assigned_consultant','interest_tags','remarks',
         'customer','converted_booking'],
        as_dict=True)

    if not lead:
        # Try mobile match via User record
        mobile = frappe.db.get_value('User', user, 'mobile_no')
        if mobile:
            lead = frappe.db.get_value('Travel Lead',
                {'mobile_no': mobile},
                ['name','full_name','mobile_no','status','email_id',
                 'suggested_package','preferred_month','pax_count',
                 'assigned_consultant','interest_tags','remarks',
                 'customer','converted_booking'],
                as_dict=True)

    if not lead:
        return None

    # Bookings linked to this lead's customer account
    bookings = []
    customer = lead.get('customer') or frappe.db.get_value('Customer', {'customer_name': lead.get('full_name')}, 'name')
    if customer:
        bookings = frappe.get_all('Booking',
            filters={'customer': customer},
            fields=['name','tour_package','departure_date','total_pax',
                    'base_amount','gst_amount','grand_total','creation'],
            order_by='creation desc')

    # Visa applications for bookings
    visas = []
    if bookings:
        bk_names = [b.name for b in bookings]
        visas = frappe.get_all('Visa Application',
            filters={'booking': ['in', bk_names]},
            fields=['name','booking','applicant_name','visa_type',
                    'destination_country','status','departure_date',
                    'submission_deadline'],
            order_by='creation desc')

    # Package details for suggested package
    package_details = None
    if lead.get('suggested_package'):
        package_details = frappe.db.get_value('Tour Package',
            lead['suggested_package'],
            ['name','package_name','tour_type','destination',
             'duration_days','duration_nights','visa_required'],
            as_dict=True)

    return {
        'lead': lead,
        'bookings': bookings,
        'visas': visas,
        'package_details': package_details,
        'customer': customer,
    }


@frappe.whitelist()
def update_lead_enquiry(**kwargs):
    if frappe.session.user == 'Guest':
        frappe.throw("Login required", frappe.AuthenticationError)
    lead_name = kwargs.get('lead_name')
    if not lead_name or not frappe.db.exists('Travel Lead', lead_name):
        return {'success': False, 'error': 'Lead not found'}
    # Verify this lead belongs to the current user
    owner_email = frappe.db.get_value('Travel Lead', lead_name, 'email_id')
    if owner_email != frappe.session.user:
        return {'success': False, 'error': 'Unauthorized'}
    doc = frappe.get_doc('Travel Lead', lead_name)
    for f in ['full_name','mobile_no','pax_count','preferred_month',
              'suggested_package','remarks','interest_tags']:
        if kwargs.get(f) is not None:
            setattr(doc, f, kwargs[f])
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return {'success': True}


@frappe.whitelist(allow_guest=True)
def portal_login(**kwargs):
    mobile = kwargs.get('mobile', '').strip()
    password = kwargs.get('password', '').strip()
    if not mobile or not password:
        return {'success': False, 'error': 'Mobile and password required'}
    try:
        lead = frappe.db.get_value('Travel Lead',
            {'mobile_no': mobile}, ['name','email_id','full_name'], as_dict=True)
        if not lead or not lead.email_id:
            return {'success': False, 'error': 'Account not found'}
        from frappe.auth import LoginManager
        lm = LoginManager()
        lm.authenticate(user=lead.email_id, pwd=password)
        lm.post_login()
        return {'success': True, 'redirect': '/travel_enquiry', 'full_name': lead.full_name}
    except frappe.AuthenticationError:
        return {'success': False, 'error': 'Invalid credentials'}
    except Exception as e:
        return {'success': False, 'error': str(e)}
