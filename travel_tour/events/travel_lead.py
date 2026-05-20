import frappe

def on_update(doc, method=None):
    """Create portal user when a Travel Lead is saved with email."""
    email = doc.get("email_id") or doc.get("email") or ""
    mobile = doc.get("mobile_no") or doc.get("phone") or doc.get("mobile") or ""
    if not email or not mobile:
        return
    if frappe.db.exists("User", email):
        return
    try:
        parts = (doc.get("lead_name") or doc.get("full_name") or "Customer").split()
        user = frappe.get_doc({
            "doctype": "User",
            "email": email,
            "first_name": parts[0],
            "last_name": " ".join(parts[1:]) if len(parts) > 1 else "",
            "mobile_no": mobile,
            "user_type": "Website User",
            "enabled": 1,
            "send_welcome_email": 0,
            "new_password": frappe.generate_hash(length=20),
        })
        user.flags.ignore_permissions = True
        user.insert()
        frappe.db.commit()
    except Exception as e:
        frappe.log_error(str(e), "Travel Lead User Creation")

after_insert = on_update
