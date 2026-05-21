import frappe

def get_context(context):
    context.no_cache = 1
    context.user = frappe.session.user
    context.is_guest = frappe.session.user == 'Guest'

@frappe.whitelist()
def get_portal_data():
    if frappe.session.user == 'Guest':
        frappe.throw("Please login", frappe.AuthenticationError)

    lead = frappe.db.get_value('Travel Lead',
        {'email_id': frappe.session.user},
        ['name','full_name','mobile_no','status','email_id',
         'suggested_package','preferred_month','pax_count'],
        as_dict=True)

    if not lead:
        return None

    bookings = frappe.get_all('Booking',
        filters={'travel_lead': lead.name},
        fields=['name','tour_package','travel_date','status','total_amount','pax_count'],
        order_by='creation desc') if frappe.db.table_exists('tabBooking') else []

    visas = frappe.get_all('Visa Application',
        filters={'booking': ['in', [b.name for b in bookings]]},
        fields=['name','booking','pax_name','destination','status']
    ) if frappe.db.table_exists('tabVisa Application') and bookings else []

    return {
        'lead': lead,
        'bookings': bookings,
        'visas': visas
    }

@frappe.whitelist(allow_guest=True)
def submit_enquiry(**kwargs):
    try:
        doc = frappe.get_doc({
            'doctype': 'Travel Lead',
            'full_name': kwargs.get('full_name', ''),
            'email_id': kwargs.get('email', ''),
            'mobile_no': kwargs.get('mobile', ''),
            'suggested_package': kwargs.get('destination', ''),
            'preferred_month': kwargs.get('travel_month', ''),
            'pax_count': kwargs.get('pax_count', 1),
            'status': 'Open',
            'source': 'Website'
        })
        doc.flags.ignore_hooks = True
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
        return {'success': True, 'name': doc.name}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), 'submit_enquiry Error')
        return {'success': False, 'error': str(e)}
