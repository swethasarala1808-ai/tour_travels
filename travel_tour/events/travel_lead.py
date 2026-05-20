import frappe
import random
import string

def on_update(doc, method):
    """Auto-create portal user when Travel Lead is saved with email"""
    if not doc.email_id:
        return
    
    if frappe.db.exists("User", doc.email_id):
        return
    
    try:
        # Generate password = last 4 digits of mobile
        password = doc.mobile_no[-4:] if doc.mobile_no else '0000'
        
        user = frappe.get_doc({
            "doctype": "User",
            "email": doc.email_id,
            "first_name": doc.full_name or doc.name,
            "enabled": 1,
            "user_type": "Website User",
            "send_welcome_email": 0,
            "roles": [{"role": "Customer"}]
        })
        user.insert(ignore_permissions=True)
        user.new_password = password
        user.save(ignore_permissions=True)
        frappe.db.commit()
        
        frappe.logger().info(f"Portal user created for {doc.email_id} | password: {password}")
    except Exception as e:
        frappe.log_error(str(e), "Travel Lead User Creation")
