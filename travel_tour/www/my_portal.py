"""
travel_tour/www/my_portal.py
Customer Portal — Mobile + Password login
"""
import frappe
import hashlib
import random
import string


def get_context(context):
    context.no_cache = 1
    context.show_sidebar = False
    if frappe.session.user and frappe.session.user != "Guest":
        mobile = frappe.db.get_value("User", frappe.session.user, "mobile_no")
        if mobile and frappe.db.exists("Travel Lead", {"mobile": mobile}):
            frappe.local.flags.redirect_location = "/travel_enquiry"
            raise frappe.Redirect


@frappe.whitelist(allow_guest=True)
def portal_login(mobile, password):
    mobile = (mobile or "").strip()
    password = (password or "").strip()
    if not mobile or not password:
        return {"success": False, "error": "Mobile and password are required."}

    # Check Travel Lead exists
    lead = frappe.db.get_value(
        "Travel Lead", {"mobile": mobile},
        ["name", "lead_name", "portal_password_hash"],
        as_dict=True,
    )
    if not lead:
        # Also try matching by mobile_no field name variations
        lead = frappe.db.get_value(
            "Travel Lead", {"mobile_no": mobile},
            ["name", "lead_name", "portal_password_hash"],
            as_dict=True,
        )
    if not lead:
        return {"success": False,
                "error": "Mobile not registered. Please contact us."}

    stored = lead.get("portal_password_hash") or ""
    if not stored:
        if password != mobile[-4:]:
            return {"success": False,
                    "error": "Incorrect password. Default = last 4 digits of mobile."}
    else:
        if _hash(password) != stored:
            return {"success": False, "error": "Incorrect password."}

    user = _get_or_create_user(mobile, lead.lead_name)
    if not user:
        return {"success": False, "error": "Account error. Contact support."}

    frappe.local.login_manager.login_as(user)
    return {"success": True}


@frappe.whitelist(allow_guest=True)
def reset_portal_password(mobile):
    mobile = (mobile or "").strip()
    lead = frappe.db.get_value("Travel Lead", {"mobile": mobile},
                               ["name", "lead_name"], as_dict=True)
    if not lead:
        return {"success": False, "error": "Mobile not registered."}
    new_pw = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    try:
        frappe.db.set_value("Travel Lead", lead.name,
                            "portal_password_hash", _hash(new_pw))
        frappe.db.commit()
    except Exception:
        pass
    frappe.log_error(f"Portal PW Reset | Mobile:{mobile} | PW:{new_pw}",
                     "Portal Password Reset")
    return {"success": True}


@frappe.whitelist()
def change_portal_password(old_password, new_password):
    if frappe.session.user == "Guest":
        return {"success": False}
    mobile = frappe.db.get_value("User", frappe.session.user, "mobile_no")
    if not mobile:
        return {"success": False}
    lead = frappe.db.get_value("Travel Lead", {"mobile": mobile},
                               ["name", "portal_password_hash"], as_dict=True)
    if not lead:
        return {"success": False}
    stored = lead.portal_password_hash or _hash(mobile[-4:])
    if _hash(old_password) != stored:
        return {"success": False, "error": "Current password incorrect."}
    if len(new_password) < 6:
        return {"success": False, "error": "Minimum 6 characters."}
    frappe.db.set_value("Travel Lead", lead.name,
                        "portal_password_hash", _hash(new_password))
    frappe.db.commit()
    return {"success": True}


def _hash(pw):
    return hashlib.sha256(("tt_salt_2025_" + pw).encode()).hexdigest()


def _get_or_create_user(mobile, name):
    existing = frappe.db.get_value("User", {"mobile_no": mobile}, "name")
    if existing:
        frappe.db.set_value("User", existing, "enabled", 1)
        return existing
    email = f"portal_{mobile}@tourtravel.internal"
    try:
        u = frappe.get_doc({
            "doctype": "User",
            "email": email,
            "first_name": (name or "Customer").split()[0],
            "mobile_no": mobile,
            "user_type": "Website User",
            "enabled": 1,
            "send_welcome_email": 0,
            "new_password": frappe.generate_hash(length=20),
            "roles": [{"role": "Customer"}],
        })
        u.flags.ignore_permissions = True
        u.insert()
        frappe.db.commit()
        return u.name
    except Exception as e:
        frappe.log_error(str(e), "Portal user creation")
        return None
