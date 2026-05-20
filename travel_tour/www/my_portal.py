"""
travel_tour/www/my_portal.py
Customer Login — mobile + password, no OTP.
Uses real Travel Lead doctype (tabTravel Lead exists in DB).
"""
import frappe
import hashlib
import random
import string


def get_context(context):
    context.no_cache = 1
    context.show_sidebar = False
    if frappe.session.user and frappe.session.user != "Guest":
        mobile = frappe.db.get_value("User", frappe.session.user, "mobile_no") or ""
        email  = frappe.session.user
        lead = (
            frappe.db.get_value("Travel Lead", {"email_id": email}, "name") or
            (frappe.db.get_value("Travel Lead", {"mobile_no": mobile}, "name") if mobile else None)
        )
        if lead:
            frappe.local.flags.redirect_location = "/travel_enquiry"
            raise frappe.Redirect


@frappe.whitelist(allow_guest=True)
def portal_login(mobile, password):
    mobile   = str(mobile or "").strip().replace(" ", "")
    password = str(password or "").strip()

    if not mobile or not password:
        return {"success": False, "error": "Mobile and password are required."}

    meta = frappe.get_meta("Travel Lead")
    real_fields = {f.fieldname for f in meta.fields}
    mobile_field = "mobile_no" if "mobile_no" in real_fields else ("phone" if "phone" in real_fields else "name")

    lead = frappe.db.get_value(
        "Travel Lead", {mobile_field: mobile},
        ["name", "lead_name", "full_name", "email_id", "portal_password_hash"],
        as_dict=True,
    )
    if not lead:
        return {"success": False, "error": "Mobile number not registered. Please contact us."}

    stored_hash = (lead.get("portal_password_hash") or "").strip()
    if not stored_hash:
        if password != mobile[-4:]:
            return {"success": False, "error": f"Incorrect password. Default is last 4 digits of mobile ({mobile[-4:]})."}
    else:
        if _hash_pw(password) != stored_hash:
            return {"success": False, "error": "Incorrect password."}

    display_name = lead.get("lead_name") or lead.get("full_name") or "Customer"
    email = lead.get("email_id") or f"portal_{mobile}@tourtravel.internal"
    user  = _get_or_create_portal_user(mobile, display_name, email)
    if not user:
        return {"success": False, "error": "Account setup error. Please contact support."}

    try:
        frappe.local.login_manager.login_as(user)
    except Exception as e:
        frappe.log_error(str(e), "portal_login error")
        return {"success": False, "error": "Login failed. Please try again."}

    return {"success": True, "redirect": "/travel_enquiry"}


@frappe.whitelist(allow_guest=True)
def reset_portal_password(mobile):
    mobile = str(mobile or "").strip().replace(" ", "")
    meta = frappe.get_meta("Travel Lead")
    real_fields = {f.fieldname for f in meta.fields}
    mobile_field = "mobile_no" if "mobile_no" in real_fields else "phone"

    lead = frappe.db.get_value("Travel Lead", {mobile_field: mobile},
        ["name", "lead_name", "full_name"], as_dict=True)
    if not lead:
        return {"success": False, "error": "Mobile number not registered."}

    new_pw = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    if "portal_password_hash" in real_fields:
        frappe.db.set_value("Travel Lead", lead.name, "portal_password_hash", _hash_pw(new_pw))
        frappe.db.commit()

    frappe.log_error(
        f"Password Reset — Mobile: {mobile} | Name: {lead.get('lead_name') or lead.get('full_name')} | Password: {new_pw}",
        "Portal Password Reset",
    )
    return {"success": True}


@frappe.whitelist()
def change_portal_password(old_password, new_password):
    if frappe.session.user == "Guest":
        return {"success": False}
    mobile = frappe.db.get_value("User", frappe.session.user, "mobile_no") or ""
    email  = frappe.session.user
    meta = frappe.get_meta("Travel Lead")
    real_fields = {f.fieldname for f in meta.fields}
    mobile_field = "mobile_no" if "mobile_no" in real_fields else "phone"

    lead = (
        frappe.db.get_value("Travel Lead", {"email_id": email}, ["name","portal_password_hash"], as_dict=True) or
        (frappe.db.get_value("Travel Lead", {mobile_field: mobile}, ["name","portal_password_hash"], as_dict=True) if mobile else None)
    )
    if not lead:
        return {"success": False, "error": "Account not found."}

    stored = (lead.get("portal_password_hash") or "").strip() or _hash_pw(mobile[-4:] if mobile else "0000")
    if _hash_pw(old_password) != stored:
        return {"success": False, "error": "Current password is incorrect."}
    if len(str(new_password)) < 6:
        return {"success": False, "error": "New password must be at least 6 characters."}

    if "portal_password_hash" in real_fields:
        frappe.db.set_value("Travel Lead", lead.name, "portal_password_hash", _hash_pw(new_password))
        frappe.db.commit()
        return {"success": True}
    return {"success": False, "error": "Password field not available."}


def _hash_pw(password):
    return hashlib.sha256(("tt_portal_salt_2024_" + str(password)).encode()).hexdigest()


def _get_or_create_portal_user(mobile, full_name, email):
    existing = frappe.db.get_value("User", {"mobile_no": mobile}, "name")
    if existing:
        frappe.db.set_value("User", existing, "enabled", 1)
        return existing
    if frappe.db.exists("User", email):
        frappe.db.set_value("User", email, "enabled", 1)
        return email
    try:
        parts = str(full_name or "Customer").split()
        user = frappe.get_doc({
            "doctype": "User", "email": email,
            "first_name": parts[0],
            "last_name": " ".join(parts[1:]) if len(parts) > 1 else "",
            "mobile_no": mobile, "user_type": "Website User",
            "enabled": 1, "send_welcome_email": 0,
            "new_password": frappe.generate_hash(length=20),
        })
        user.flags.ignore_permissions = True
        user.insert()
        frappe.db.commit()
        return user.name
    except Exception as e:
        frappe.log_error(str(e), "Portal user creation error")
        return None
