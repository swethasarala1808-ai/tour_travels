"""
travel_tour/www/my_portal.py
Customer Portal — Mobile + Password login (no OTP)
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
    """Authenticate portal customer by mobile + password."""
    mobile   = (mobile or "").strip()
    password = (password or "").strip()

    if not mobile or not password:
        return {"success": False, "error": "Mobile and password are required."}

    lead = frappe.db.get_value(
        "Travel Lead", {"mobile": mobile},
        ["name", "lead_name", "portal_password_hash"],
        as_dict=True,
    )
    if not lead:
        return {"success": False, "error": "Mobile number not registered. Please contact us."}

    stored_hash = lead.get("portal_password_hash")
    if not stored_hash:
        # Default password = last 4 digits of mobile (first-time login)
        if password != mobile[-4:]:
            return {"success": False, "error": "Incorrect password. Default is last 4 digits of your mobile number."}
    else:
        if _hash_pw(password) != stored_hash:
            return {"success": False, "error": "Incorrect password."}

    user = _get_or_create_portal_user(mobile, lead.lead_name)
    if not user:
        return {"success": False, "error": "Account setup error. Please contact support."}

    frappe.local.login_manager.login_as(user)
    return {"success": True}


@frappe.whitelist(allow_guest=True)
def reset_portal_password(mobile):
    """Generate a new password and send via WhatsApp."""
    mobile = (mobile or "").strip()
    lead = frappe.db.get_value(
        "Travel Lead", {"mobile": mobile},
        ["name", "lead_name"], as_dict=True,
    )
    if not lead:
        return {"success": False, "error": "Mobile number not registered."}

    new_pw = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    frappe.db.set_value("Travel Lead", lead.name, "portal_password_hash", _hash_pw(new_pw))
    frappe.db.commit()

    try:
        settings = frappe.get_single("Travel Tour Settings")
        if getattr(settings, "whatsapp_enabled", False):
            from travel_tour.api.whatsapp import send_message
            send_message(mobile, "portal_password_reset", {
                "name": lead.lead_name,
                "password": new_pw,
            })
        else:
            # Dev fallback: log to error log so admin can retrieve it
            frappe.log_error(
                f"Portal PW Reset — Mobile: {mobile} | New Password: {new_pw}",
                "Portal Password Reset (WhatsApp not configured)",
            )
    except Exception as e:
        frappe.log_error(str(e), "Portal PW Reset Error")

    return {"success": True}


@frappe.whitelist()
def change_portal_password(old_password, new_password):
    """Logged-in customer changes their portal password."""
    if frappe.session.user == "Guest":
        return {"success": False}

    mobile = frappe.db.get_value("User", frappe.session.user, "mobile_no")
    if not mobile:
        return {"success": False}

    lead = frappe.db.get_value(
        "Travel Lead", {"mobile": mobile},
        ["name", "portal_password_hash"], as_dict=True,
    )
    if not lead:
        return {"success": False}

    stored = lead.portal_password_hash or _hash_pw(mobile[-4:])
    if _hash_pw(old_password) != stored:
        return {"success": False, "error": "Current password is incorrect."}

    if len(new_password) < 6:
        return {"success": False, "error": "New password must be at least 6 characters."}

    frappe.db.set_value("Travel Lead", lead.name, "portal_password_hash", _hash_pw(new_password))
    frappe.db.commit()
    return {"success": True}


# ── helpers ────────────────────────────────────────────────────────────────────

def _hash_pw(password):
    return hashlib.sha256(("tt_portal_salt_2024_" + password).encode()).hexdigest()


def _get_or_create_portal_user(mobile, name):
    existing = frappe.db.get_value("User", {"mobile_no": mobile}, "name")
    if existing:
        frappe.db.set_value("User", existing, "enabled", 1)
        return existing

    email = f"portal_{mobile}@tourtravel.internal"
    try:
        user = frappe.get_doc({
            "doctype": "User",
            "email": email,
            "first_name": (name or "Customer").split()[0],
            "last_name": " ".join((name or "Customer").split()[1:]) or "",
            "mobile_no": mobile,
            "user_type": "Website User",
            "enabled": 1,
            "send_welcome_email": 0,
            "new_password": frappe.generate_hash(length=20),
            "roles": [{"role": "Customer"}],
        })
        user.flags.ignore_permissions = True
        user.insert()
        frappe.db.commit()
        return user.name
    except Exception as e:
        frappe.log_error(str(e), "Portal user creation error")
        return None
