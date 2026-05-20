import frappe

def on_update(doc, method=None):
    if not doc.email_id or not doc.mobile_no:
        return
    user_email = doc.email_id
    if frappe.db.exists("User", user_email):
        return
    try:
        user = frappe.get_doc({
            "doctype": "User",
            "email": user_email,
            "first_name": doc.full_name or doc.name,
            "enabled": 1,
            "user_type": "Website User",
            "send_welcome_email": 0
        })
        user.insert(ignore_permissions=True)
        from frappe.utils.password import update_password
        update_password(user_email, doc.mobile_no[-4:])
        frappe.db.commit()
        frappe.logger().info(f"Portal user created: {user_email}")
    except Exception as e:
        frappe.log_error(str(e), "Travel Lead User Creation")

after_insert = on_update
