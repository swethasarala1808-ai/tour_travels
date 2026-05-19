import frappe

def get_context(context):
    if frappe.session.user == 'Guest':
        frappe.local.flags.redirect_location = '/login?redirect-to=/founder_dash'
        raise frappe.Redirect

    # Check founder access
    user_roles = frappe.get_roles(frappe.session.user)
    allowed = any(r in user_roles for r in ['System Manager', 'Administrator', 'Founder'])
    if not allowed:
        frappe.throw('Access denied. Founder role required.', frappe.PermissionError)

    context.no_cache = 1
    context.user_email = frappe.session.user
    context.user_name = frappe.db.get_value('User', frappe.session.user, 'full_name') or 'Founder'

    # Leads from ERPNext
    leads = frappe.get_all(
        'Lead',
        fields=['name', 'lead_name', 'email_id', 'mobile_no', 'status', 'creation'],
        order_by='creation desc',
        limit=50
    )
    context.leads = leads
    context.lead_count = len(leads)
    context.open_leads = len([l for l in leads if l.status in ['Open', 'Lead', 'Interested']])

    # Customers from ERPNext
    customers = frappe.get_all(
        'Customer',
        fields=['name', 'customer_name', 'mobile_no', 'creation'],
        order_by='creation desc',
        limit=50
    )
    context.customers = customers
    context.customer_count = len(customers)
    context.bookings = []
    context.total_revenue = 0
