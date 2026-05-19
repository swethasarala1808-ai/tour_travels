import frappe

def get_context(context):
    if frappe.session.user == 'Guest':
        frappe.local.flags.redirect_location = '/login?redirect-to=/my_portal'
        raise frappe.Redirect

    context.no_cache = 1

    # Find Travel Lead linked to this user's email
    lead = frappe.db.get_value(
        'Travel Lead',
        {'email_id': frappe.session.user},
        ['name', 'full_name', 'email_id', 'mobile_no', 'status'],
        as_dict=True
    )

    context.lead = lead
    context.user_email = frappe.session.user
    context.user_name = frappe.db.get_value('User', frappe.session.user, 'full_name')

    if not lead:
        context.no_lead = True
        return

    # Get bookings for this lead
    bookings = frappe.get_all(
        'Booking',
        filters={'travel_lead': lead.name},
        fields=['name', 'tour_package', 'travel_date', 'status', 'total_amount'],
        order_by='creation desc',
        limit=10
    )
    context.bookings = bookings

    # Get visa applications
    visas = frappe.get_all(
        'Visa Application',
        filters={'booking': ['in', [b.name for b in bookings]]},
        fields=['name', 'pax_name', 'destination', 'status', 'passport_no'],
        limit=20
    ) if bookings else []
    context.visas = visas
