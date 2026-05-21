import frappe

def get_context(context):
    if frappe.session.user == 'Guest':
        frappe.local.flags.redirect_location = '/login?redirect-to=/founder_dash'
        raise frappe.Redirect

    roles = frappe.get_roles(frappe.session.user)
    if not any(r in roles for r in ['System Manager', 'Administrator', 'Founder']):
        frappe.throw("Access denied", frappe.PermissionError)

    context.no_cache = 1
    context.user = frappe.session.user
    context.user_name = frappe.db.get_value('User', frappe.session.user, 'full_name') or 'Founder'
