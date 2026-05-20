import frappe

@frappe.whitelist(allow_guest=True)
def portal_login(mobile, password):
    mobile = str(mobile).strip()
    lead = frappe.db.get_value('Travel Lead', {'mobile_no': mobile},
        ['name','full_name','mobile_no','email_id'], as_dict=True)
    if not lead:
        return {"success": False, "error": "Mobile number not registered"}

    # Check if user has set a custom password
    user_email = lead.email_id or f"{mobile}@portal.local"
    
    # Ensure user exists
    if not frappe.db.exists("User", user_email):
        _create_portal_user(lead, mobile)

    # Verify password via Frappe
    try:
        from frappe.utils.password import check_password
        check_password(user_email, password)
        return {"success": True, "name": lead.full_name, "lead": lead.name}
    except Exception:
        # Fallback: check last 4 digits (first-time login)
        if password == mobile[-4:]:
            return {"success": True, "name": lead.full_name, "lead": lead.name, "must_set_password": True}
        return {"success": False, "error": "Invalid password"}

@frappe.whitelist(allow_guest=True)
def set_password(mobile, old_password, new_password, confirm_password):
    if new_password != confirm_password:
        return {"success": False, "error": "Passwords do not match"}
    if len(new_password) < 6:
        return {"success": False, "error": "Password must be at least 6 characters"}

    mobile = str(mobile).strip()
    lead = frappe.db.get_value('Travel Lead', {'mobile_no': mobile},
        ['name','email_id'], as_dict=True)
    if not lead:
        return {"success": False, "error": "Mobile not registered"}

    user_email = lead.email_id or f"{mobile}@portal.local"
    if not frappe.db.exists("User", user_email):
        return {"success": False, "error": "User not found"}

    # Verify old password = last 4 digits
    if old_password != mobile[-4:]:
        try:
            from frappe.utils.password import check_password
            check_password(user_email, old_password)
        except Exception:
            return {"success": False, "error": "Current password is incorrect"}

    from frappe.utils.password import update_password
    update_password(user_email, new_password)
    frappe.db.commit()
    return {"success": True}

@frappe.whitelist(allow_guest=True)
def forgot_password(mobile):
    mobile = str(mobile).strip()
    lead = frappe.db.get_value('Travel Lead', {'mobile_no': mobile},
        ['name','email_id','full_name'], as_dict=True)
    if not lead:
        return {"success": False, "error": "Mobile number not registered"}
    # Reset password to last 4 digits
    user_email = lead.email_id or f"{mobile}@portal.local"
    if frappe.db.exists("User", user_email):
        from frappe.utils.password import update_password
        update_password(user_email, mobile[-4:])
        frappe.db.commit()
    return {"success": True, "message": f"Password reset to last 4 digits of your mobile: {mobile[-4:]}"}

def _create_portal_user(lead, mobile):
    user_email = lead.email_id or f"{mobile}@portal.local"
    user = frappe.get_doc({
        "doctype": "User",
        "email": user_email,
        "first_name": lead.full_name or mobile,
        "enabled": 1,
        "user_type": "Website User",
        "send_welcome_email": 0
    })
    user.insert(ignore_permissions=True)
    from frappe.utils.password import update_password
    update_password(user_email, mobile[-4:])
    frappe.db.commit()

@frappe.whitelist(allow_guest=True)
def get_package_itinerary(package):
    try:
        return frappe.get_all('Itinerary Day',
            filters={'parent': package},
            fields=['day_number','title','description','meals'],
            order_by='day_number asc')
    except Exception:
        return []
