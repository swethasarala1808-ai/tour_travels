import frappe

def get_context(context):
    if frappe.session.user == 'Guest':
        frappe.local.flags.redirect_location = '/login?redirect-to=/my_portal'
        raise frappe.Redirect

    context.no_cache = 1
    context.user_email = frappe.session.user
    context.user_name = frappe.db.get_value('User', frappe.session.user, 'full_name') or 'Traveller'

    # Use ERPNext's built-in Lead doctype
    lead = frappe.db.get_value(
        'Lead',
        {'email_id': frappe.session.user},
        ['name', 'lead_name', 'email_id', 'mobile_no', 'status', 'lead_owner'],
        as_dict=True
    )

    if lead:
        context.lead = lead
        context.no_lead = False
        context.full_name = lead.lead_name
        context.mobile = lead.mobile_no
    else:
        # Also check Customer doctype
        customer = frappe.db.get_value(
            'Customer',
            {'email_id': frappe.session.user},
            ['name', 'customer_name', 'mobile_no'],
            as_dict=True
        )
        if customer:
            context.lead = frappe._dict({
                'name': customer.name,
                'lead_name': customer.customer_name,
                'email_id': frappe.session.user,
                'mobile_no': customer.mobile_no,
                'status': 'Customer'
            })
            context.no_lead = False
            context.full_name = customer.customer_name
        else:
            context.lead = None
            context.no_lead = True
            context.full_name = context.user_name

    context.bookings = []
    context.visas = []
