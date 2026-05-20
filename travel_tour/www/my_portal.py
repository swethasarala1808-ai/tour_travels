import frappe

def get_context(context):
    context.no_cache = 1
    # Already logged in as a Travel Lead user? Redirect to dashboard
    if frappe.session.user != "Guest":
        mobile = frappe.db.get_value("User", frappe.session.user, "mobile_no") or                  frappe.db.get_value("User", frappe.session.user, "mobile")
        if mobile and frappe.db.exists("Travel Lead", {"mobile": mobile}):
            frappe.local.flags.redirect_location = "/travel_enquiry"
            raise frappe.Redirect


@frappe.whitelist(allow_guest=True)
def portal_login(mobile, password):
    """Authenticate customer by mobile + password and create Frappe session."""
    try:
        mobile   = str(mobile).strip().replace(" ", "")
        password = str(password).strip()

        lead = frappe.db.get_value(
            "Travel Lead",
            {"mobile": mobile},
            ["name", "full_name", "mobile", "email_id", "status"],
            as_dict=True,
        )

        if not lead:
            return {"success": False, "error": "Mobile number not registered. Contact us to get access."}

        # Determine portal user email
        user_email = lead.email_id or f"portal_{mobile}@traveltour.local"

        # Auto-create portal user if missing
        if not frappe.db.exists("User", user_email):
            _create_portal_user(mobile, lead.full_name, user_email)

        # Verify password
        default_pw = mobile[-4:]
        password_ok = False

        # Try Frappe password check first
        try:
            from frappe.utils.password import check_password
            check_password(user_email, password)
            password_ok = True
        except Exception:
            # Fall back to default (last 4 digits)
            if password == default_pw:
                password_ok = True

        if not password_ok:
            return {"success": False, "error": f"Incorrect password. Default password is last 4 digits of your mobile number."}

        # Create Frappe session (this is the key step - logs the user in)
        frappe.local.login_manager.login_as(user_email)
        frappe.db.commit()

        return {
            "success":  True,
            "name":     lead.full_name,
            "lead":     lead.name,
            "redirect": "/travel_enquiry",
        }

    except frappe.exceptions.AuthenticationError:
        return {"success": False, "error": "Authentication failed."}
    except Exception as e:
        frappe.log_error(str(e), "Portal Login Error")
        return {"success": False, "error": "Login failed. Please try again."}


@frappe.whitelist(allow_guest=True)
def reset_portal_password(mobile):
    """Reset password to last 4 digits and notify via WhatsApp."""
    mobile = str(mobile).strip()
    lead = frappe.db.get_value(
        "Travel Lead", {"mobile": mobile}, ["name", "full_name", "email_id"], as_dict=True
    )
    if not lead:
        return {"success": False, "error": "Mobile number not registered."}

    user_email = lead.email_id or f"portal_{mobile}@traveltour.local"
    new_pw = mobile[-4:]

    try:
        if frappe.db.exists("User", user_email):
            from frappe.utils.password import update_password
            update_password(user_email, new_pw)
            frappe.db.commit()
    except Exception as e:
        frappe.log_error(str(e), "Portal PW Reset Error")

    # Try WhatsApp notification
    try:
        from travel_tour.api.whatsapp import send_message
        send_message(mobile, "portal_password_reset", {
            "name": lead.full_name, "password": new_pw
        })
    except Exception:
        frappe.logger().info(f"PW reset for {mobile}: {new_pw} (WhatsApp not configured)")

    return {"success": True}


@frappe.whitelist()
def change_portal_password(old_password, new_password):
    """Logged-in user changes their portal password."""
    if frappe.session.user == "Guest":
        return {"success": False}

    user_email = frappe.session.user
    try:
        from frappe.utils.password import check_password, update_password
        check_password(user_email, old_password)
        if len(new_password) < 6:
            return {"success": False, "error": "Password must be at least 6 characters."}
        update_password(user_email, new_password)
        frappe.db.commit()
        return {"success": True}
    except Exception:
        return {"success": False, "error": "Current password is incorrect."}


def _create_portal_user(mobile, full_name, user_email):
    """Create a Website User for portal access."""
    try:
        name_parts = (full_name or "Customer").split()
        user = frappe.get_doc({
            "doctype":          "User",
            "email":            user_email,
            "first_name":       name_parts[0],
            "last_name":        " ".join(name_parts[1:]) if len(name_parts) > 1 else "",
            "mobile_no":        mobile,
            "enabled":          1,
            "user_type":        "Website User",
            "send_welcome_email": 0,
            "roles":            [{"role": "Customer"}],
        })
        user.flags.ignore_permissions = True
        user.insert()
        from frappe.utils.password import update_password
        update_password(user_email, mobile[-4:])
        frappe.db.commit()
    except Exception as e:
        frappe.log_error(str(e), "Portal User Creation Error")
