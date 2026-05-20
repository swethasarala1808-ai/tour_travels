import frappe

def get_context(context):
    context.no_cache = 1
    # This page serves as standalone HTML - no server-side auth required
    # The JS handles auth via frappe API calls
    context.user = frappe.session.user
