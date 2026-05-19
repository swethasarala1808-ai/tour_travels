import frappe

def get_context(context):
    context.no_cache = 1
    context.user = frappe.session.user
    context.is_guest = frappe.session.user == 'Guest'

    if not context.is_guest:
        context.user_name = frappe.db.get_value('User', frappe.session.user, 'full_name') or ''
        context.user_email = frappe.session.user
    else:
        context.user_name = ''
        context.user_email = ''
