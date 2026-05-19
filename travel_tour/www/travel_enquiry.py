import frappe

def get_context(context):
    context.no_cache = 1
    context.show_sidebar = False
    # Allow guest access
    context.packages = frappe.get_all(
        'Tour Package',
        fields=['name', 'package_name', 'tour_type', 'destination', 'duration_days', 'duration_nights'],
        order_by='package_name asc',
        ignore_permissions=True
    )
