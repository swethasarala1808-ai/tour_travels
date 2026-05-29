"""
travel_tour/www/my_portal.py  — v3 SAFE
Mobile + password login. Does NOT crash if any field is missing.
"""
import frappe
import hashlib
import random
import string


def get_context(context):
    context.no_cache = 1
    context.show_sidebar = False
    if frappe.session.user and frappe.session.user != "Guest":
        try:
            mobile = frappe.db.get_value("User", frappe.session.user, "mobile_no") or ""
            lead = _find_lead_by_email_or_mobile(frappe.session.user, mobile)
            if lead:
                frappe.local.flags.redirect_location = "/travel_enquiry"
                raise frappe.Redirect
        except frappe.Redirect:
            raise
        except Exception:
            pass


def _find_lead_by_mobile(mobile):
    for field in ["mobile_no", "phone", "mobile", "contact_mobile"]:
        try:
            r = frappe.db.get_value("Travel Lead", {field: mobile}, "name")
            if r:
                return r
        except Exception:
            continue
    try:
        r = frappe.db.sql(
            "SELECT name FROM `tabTravel Lead` WHERE mobile_no=%s OR phone=%s LIMIT 1",
            (mobile, mobile)
        )
        return r[0][0] if r else None
    except Exception:
        return None


def _find_lead_by_email_or_mobile(email, mobile):
    try:
        r = frappe.db.get_value("Travel Lead", {"email_id": email}, "name")
        if r:
            return r
    except Exception:
        pass
    if mobile:
        return _find_lead_by_mobile(mobile)
    return None


def _get_lead_doc_safe(lead_name):
    try:
        row = frappe.db.sql(
            "SELECT * FROM `tabTravel Lead` WHERE name=%s LIMIT 1",
            lead_name, as_dict=True
        )
        return row[0] if row else None
    except Exception:
        return None


def _get_or_create_portal_user(mobile, full_name, email):
    try:
        existing = frappe.db.get_value("User", {"mobile_no": mobile}, "name")
        if existing:
            frappe.db.set_value("User", existing, "enabled", 1)
            return existing
    except Exception:
        pass
    try:
        if frappe.db.exists("User", email):
            frappe.db.set_value("User", email, "enabled", 1)
            return email
    except Exception:
        pass
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
        frappe.log_error(str(e), "Portal user creation")
        return None


def _hash_pw(password):
    return hashlib.sha256(("tt_portal_salt_2024_" + str(password)).encode()).hexdigest()


@frappe.whitelist(allow_guest=True)
def portal_login(mobile, password):
    try:
        mobile   = str(mobile   or "").strip().replace(" ", "")
        password = str(password or "").strip()

        if not mobile or not password:
            return {"success": False, "error": "Mobile and password are required."}

        lead_name = _find_lead_by_mobile(mobile)
        if not lead_name:
            return {"success": False, "error": "Mobile number not registered. Please contact us."}

        lead = _get_lead_doc_safe(lead_name)
        if not lead:
            return {"success": False, "error": "Account not found."}

        stored_hash = str(lead.get("portal_password_hash") or "").strip()
        if not stored_hash:
            if password != mobile[-4:]:
                return {"success": False, "error": "Incorrect password. Default is last 4 digits of your mobile number."}
        else:
            if _hash_pw(password) != stored_hash:
                return {"success": False, "error": "Incorrect password."}

        display_name = (lead.get("lead_name") or lead.get("full_name") or
                        lead.get("customer_name") or "Customer")
        email = lead.get("email_id") or lead.get("email") or f"portal_{mobile}@tourtravel.internal"

        user = _get_or_create_portal_user(mobile, display_name, email)
        if not user:
            return {"success": False, "error": "Could not create account. Please contact support."}

        frappe.local.login_manager.login_as(user)
        return {"success": True, "redirect": "/travel_enquiry"}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "portal_login error")
        return {"success": False, "error": "Server error. Please try again."}


@frappe.whitelist(allow_guest=True)
def reset_portal_password(mobile):
    try:
        mobile = str(mobile or "").strip().replace(" ", "")
        lead_name = _find_lead_by_mobile(mobile)
        if not lead_name:
            return {"success": False, "error": "Mobile number not registered."}
        lead = _get_lead_doc_safe(lead_name)
        display_name = (lead or {}).get("lead_name") or (lead or {}).get("full_name") or "Customer"
        new_pw = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
        try:
            frappe.db.set_value("Travel Lead", lead_name, "portal_password_hash", _hash_pw(new_pw))
            frappe.db.commit()
        except Exception:
            pass
        frappe.log_error(
            f"Password Reset\nMobile: {mobile}\nName: {display_name}\nNew Password: {new_pw}",
            "Portal Password Reset",
        )
        return {"success": True}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "reset_portal_password error")
        return {"success": False, "error": "Server error. Please try again."}


@frappe.whitelist()
def change_portal_password(old_password, new_password):
    try:
        if frappe.session.user == "Guest":
            return {"success": False, "error": "Not logged in."}
        mobile = frappe.db.get_value("User", frappe.session.user, "mobile_no") or ""
        lead_name = _find_lead_by_email_or_mobile(frappe.session.user, mobile)
        if not lead_name:
            return {"success": False, "error": "Account not found."}
        lead = _get_lead_doc_safe(lead_name)
        stored = str((lead or {}).get("portal_password_hash") or "").strip()
        if not stored:
            stored = _hash_pw(mobile[-4:] if mobile else "0000")
        if _hash_pw(old_password) != stored:
            return {"success": False, "error": "Current password is incorrect."}
        if len(str(new_password)) < 6:
            return {"success": False, "error": "New password must be at least 6 characters."}
        try:
            frappe.db.set_value("Travel Lead", lead_name, "portal_password_hash", _hash_pw(new_password))
            frappe.db.commit()
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": f"Could not save: {e}"}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "change_portal_password error")
        return {"success": False, "error": "Server error."}
