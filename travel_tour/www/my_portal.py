import frappe

def get_context(context):
    context.no_cache = 1

@frappe.whitelist(allow_guest=True)
def portal_login(mobile, password):
    try:
        mobile = str(mobile).strip()
        password = str(password).strip()

        lead = frappe.db.get_value('Travel Lead',
            {'mobile_no': mobile},
            ['name','full_name','mobile_no','email_id','status'], as_dict=True)

        if not lead:
            return {'success': False, 'error': 'Mobile number not registered'}

        user_email = lead.email_id
        if not user_email:
            return {'success': False, 'error': 'No email on this account. Contact support.'}

        # Auto-create user if missing
        if not frappe.db.exists('User', user_email):
            user = frappe.get_doc({
                'doctype': 'User',
                'email': user_email,
                'first_name': lead.full_name or mobile,
                'enabled': 1,
                'user_type': 'Website User',
                'send_welcome_email': 0
            })
            user.flags.ignore_permissions = True
            user.insert(ignore_permissions=True)
            from frappe.utils.password import update_password
            update_password(user_email, mobile[-4:])
            frappe.db.commit()

        # Verify password
        ok = False
        if password == mobile[-4:]:
            ok = True
        else:
            try:
                from frappe.utils.password import check_password
                check_password(user_email, password)
                ok = True
            except Exception:
                pass

        if not ok:
            return {'success': False, 'error': 'Wrong password. Default is last 4 digits of mobile.'}

        # LOGIN the user into Frappe session
        frappe.local.login_manager.login_as(user_email)
        frappe.db.commit()

        return {'success': True, 'name': lead.full_name, 'redirect': '/travel_enquiry'}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), 'Portal Login')
        return {'success': False, 'error': str(e)}

@frappe.whitelist(allow_guest=True)
def reset_portal_password(mobile):
    mobile = str(mobile).strip()
    lead = frappe.db.get_value('Travel Lead',
        {'mobile_no': mobile}, ['name','email_id'], as_dict=True)
    if not lead or not lead.email_id:
        return {'success': False, 'error': 'Mobile not registered'}
    if frappe.db.exists('User', lead.email_id):
        from frappe.utils.password import update_password
        update_password(lead.email_id, mobile[-4:])
        frappe.db.commit()
        return {'success': True, 'message': f'Password reset to: {mobile[-4:]}'}
    return {'success': False, 'error': 'User not found'}
