import frappe
from frappe import _

def get_context(context):
    context.no_cache = 1
    context.user_email = frappe.session.user
    context.is_guest = frappe.session.user == 'Guest'
    if not context.is_guest:
        context.user_name = frappe.db.get_value('User', frappe.session.user, 'full_name') or ''
        lead = frappe.db.get_value('Travel Lead',
            {'email_id': frappe.session.user},
            ['name','full_name','email_id','mobile_no','status'], as_dict=True)
        context.lead = lead
        context.no_lead = not bool(lead)
    else:
        context.user_name = ''
        context.lead = None
        context.no_lead = True

@frappe.whitelist(allow_guest=True)
def portal_login(mobile, password):
    mobile = str(mobile).strip()
    password = str(password).strip()

    lead = frappe.db.get_value('Travel Lead',
        {'mobile_no': mobile},
        ['name','full_name','mobile_no','email_id','status'], as_dict=True)

    if not lead:
        return {'success': False, 'error': 'Mobile number not registered'}

    user_email = lead.email_id
    if not user_email:
        return {'success': False, 'error': 'No email linked to this account. Contact support.'}

    # Auto-create user if not exists
    if not frappe.db.exists('User', user_email):
        try:
            user = frappe.get_doc({
                'doctype': 'User',
                'email': user_email,
                'first_name': lead.full_name or mobile,
                'enabled': 1,
                'user_type': 'Website User',
                'send_welcome_email': 0
            })
            user.insert(ignore_permissions=True)
            from frappe.utils.password import update_password
            update_password(user_email, mobile[-4:])
            frappe.db.commit()
        except Exception as e:
            frappe.log_error(str(e), 'Portal User Creation')
            return {'success': False, 'error': 'Could not create account. Contact support.'}

    # Try password check
    default_pw = mobile[-4:]
    check_ok = False

    try:
        from frappe.utils.password import check_password
        check_password(user_email, password)
        check_ok = True
    except Exception:
        if password == default_pw:
            check_ok = True

    if not check_ok:
        return {'success': False, 'error': 'Invalid password. Use last 4 digits of your mobile for first login.'}

    # Log the user in via Frappe session
    try:
        frappe.local.login_manager.login_as(user_email)
        frappe.db.commit()
    except Exception as e:
        frappe.log_error(str(e), 'Portal Login Session')
        return {'success': False, 'error': 'Session error. Please try again.'}

    return {
        'success': True,
        'name': lead.full_name,
        'redirect': '/travel_enquiry',
        'must_set_password': (password == default_pw)
    }

@frappe.whitelist(allow_guest=True)
def reset_portal_password(mobile):
    mobile = str(mobile).strip()
    lead = frappe.db.get_value('Travel Lead',
        {'mobile_no': mobile},
        ['name','full_name','email_id'], as_dict=True)
    if not lead or not lead.email_id:
        return {'success': False, 'error': 'Mobile not registered'}
    if frappe.db.exists('User', lead.email_id):
        from frappe.utils.password import update_password
        update_password(lead.email_id, mobile[-4:])
        frappe.db.commit()
        return {'success': True, 'message': f'Password reset to last 4 digits: {mobile[-4:]}'}
    return {'success': False, 'error': 'User account not found'}
