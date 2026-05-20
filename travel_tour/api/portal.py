import frappe
import hashlib

@frappe.whitelist(allow_guest=True)
def portal_login(mobile, password):
    try:
        mobile = str(mobile).strip().replace(" ", "")
        lead = frappe.db.get_value(
            'Travel Lead',
            {'mobile_no': mobile},
            ['name', 'full_name', 'mobile_no', 'email_id'],
            as_dict=True
        )
        if not lead:
            return {"success": False, "error": "Mobile number not registered"}

        expected = mobile[-4:]
        if str(password) != expected:
            return {"success": False, "error": "Invalid password. Use last 4 digits of mobile."}

        # Create user if email exists and user doesn't exist
        if lead.email_id and not frappe.db.exists("User", lead.email_id):
            user = frappe.get_doc({
                "doctype": "User",
                "email": lead.email_id,
                "first_name": lead.full_name,
                "enabled": 1,
                "user_type": "Website User",
                "send_welcome_email": 0
            })
            user.insert(ignore_permissions=True)
            user.new_password = mobile[-4:]
            user.save(ignore_permissions=True)
            frappe.db.commit()

        return {"success": True, "name": lead.full_name, "lead": lead.name, "mobile": mobile}
    except Exception as e:
        frappe.log_error(str(e), "Portal Login Error")
        return {"success": False, "error": str(e)}

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
