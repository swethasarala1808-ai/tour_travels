import frappe

def get_context(context):
    context.no_cache = 1

@frappe.whitelist(allow_guest=True)
def portal_login(mobile, password):
    try:
        mobile = str(mobile).strip()
        password = str(password).strip()
        
        lead = frappe.db.get_value(
            'Travel Lead',
            {'mobile_no': mobile},
            ['name', 'full_name', 'mobile_no', 'email_id', 'status'],
            as_dict=True
        )
        
        if not lead:
            return {'success': False, 'error': 'Mobile number not registered'}
        
        # Check password = last 4 digits
        if password == mobile[-4:]:
            return {
                'success': True,
                'name': lead.full_name,
                'lead': lead.name,
                'redirect': '/travel_enquiry'
            }
        
        # Check custom password if user exists
        user_email = lead.email_id
        if user_email and frappe.db.exists('User', user_email):
            try:
                from frappe.utils.password import check_password
                check_password(user_email, password)
                return {
                    'success': True,
                    'name': lead.full_name,
                    'lead': lead.name,
                    'redirect': '/travel_enquiry'
                }
            except Exception:
                pass
        
        return {'success': False, 'error': 'Invalid password. Default: last 4 digits of mobile'}
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), 'Portal Login Error')
        return {'success': False, 'error': str(e)}

@frappe.whitelist(allow_guest=True)
def reset_portal_password(mobile):
    try:
        mobile = str(mobile).strip()
        lead = frappe.db.get_value('Travel Lead', {'mobile_no': mobile}, 
            ['name', 'email_id'], as_dict=True)
        if not lead:
            return {'success': False, 'error': 'Mobile not registered'}
        if lead.email_id and frappe.db.exists('User', lead.email_id):
            from frappe.utils.password import update_password
            update_password(lead.email_id, mobile[-4:])
            frappe.db.commit()
        return {'success': True, 'message': f'Password reset to: {mobile[-4:]}'}
    except Exception as e:
        return {'success': False, 'error': str(e)}
