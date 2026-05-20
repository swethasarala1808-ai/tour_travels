import frappe

def get_context(context):
    context.no_cache = 1
    # Allow both logged in and guest users
    context.user = frappe.session.user
    context.is_guest = frappe.session.user == 'Guest'
    
    if not context.is_guest:
        # Get lead info for logged-in user
        lead = frappe.db.get_value('Travel Lead',
            {'email_id': frappe.session.user},
            ['name','full_name','mobile_no','status'], as_dict=True)
        context.lead = lead
