import frappe

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
    lead = frappe.db.get_value('Travel Lead',
        {'mobile_no': mobile},
        ['name','full_name','mobile_no','email_id','status'], as_dict=True)
    if not lead:
        frappe.response['http_status_code'] = 200
        return {'success': False, 'error': 'Mobile number not registered'}

    user_email = lead.email_id or f'{mobile}@portal.local'

    # Ensure user exists
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

    # Verify password
    try:
        from frappe.utils.password import check_password
        check_password(user_email, str(password))
        frappe.local.login_manager.login_as(user_email)
        frappe.db.commit()
        return {'success': True, 'name': lead.full_name, 'redirect': '/travel_enquiry'}
    except Exception:
        # Check default password (last 4 digits)
        default_pw = mobile[-4:]
        if str(password) == default_pw:
            frappe.local.login_manager.login_as(user_email)
            frappe.db.commit()
            return {'success': True, 'name': lead.full_name,
                    'redirect': '/travel_enquiry', 'must_set_password': True}
        return {'success': False, 'error': 'Invalid password'}

@frappe.whitelist(allow_guest=True)
def reset_portal_password(mobile):
    mobile = str(mobile).strip()
    lead = frappe.db.get_value('Travel Lead',
        {'mobile_no': mobile},
        ['name','full_name','email_id'], as_dict=True)
    if not lead:
        return {'success': False, 'error': 'Mobile not registered'}
    # Reset to last 4 digits
    user_email = lead.email_id or f'{mobile}@portal.local'
    if frappe.db.exists('User', user_email):
        from frappe.utils.password import update_password
        update_password(user_email, mobile[-4:])
        frappe.db.commit()
        return {'success': True, 'message': f'Password reset to last 4 digits of your mobile'}
    return {'success': False, 'error': 'User account not found'}
