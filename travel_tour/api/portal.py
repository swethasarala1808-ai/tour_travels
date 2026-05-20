import frappe
import hashlib

@frappe.whitelist(allow_guest=True)
def portal_login(mobile, password):
    try:
        mobile = mobile.strip().replace(" ", "")
        lead = frappe.db.get_value(
            'Travel Lead',
            {'mobile_no': mobile},
            ['name', 'full_name', 'mobile_no', 'email_id'],
            as_dict=True
        )
        if not lead:
            return {"success": False, "error": "Mobile number not registered"}

        # Password = last 4 digits of mobile (default)
        expected = mobile[-4:]
        if password != expected:
            return {"success": False, "error": "Invalid password"}

        # Log in as the linked user or guest session
        return {"success": True, "name": lead.full_name, "lead": lead.name}
    except Exception as e:
        frappe.log_error(str(e), "Portal Login Error")
        return {"success": False, "error": "Login failed"}

@frappe.whitelist(allow_guest=True)
def get_package_itinerary(package):
    try:
        days = frappe.get_all(
            'Itinerary Day',
            filters={'parent': package},
            fields=['day_number', 'title', 'description', 'meals'],
            order_by='day_number asc'
        )
        return days
    except Exception:
        return []
