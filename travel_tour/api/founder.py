import frappe

@frappe.whitelist()
def get_founder_data():
    try:
        leads = frappe.get_all('Travel Lead',
            fields=['name','full_name','email_id','mobile_no','status',
                    'source','suggested_package','pax_count',
                    'preferred_month','assigned_consultant','creation'],
            order_by='creation desc', limit=100)

        bookings = []
        if frappe.db.table_exists('tabBooking'):
            bookings = frappe.get_all('Booking',
                fields=['name','travel_lead','tour_package',
                        'travel_date','status','total_amount','pax_count'],
                order_by='creation desc', limit=100)

        packages = []
        if frappe.db.table_exists('tabTour Package'):
            packages = frappe.get_all('Tour Package',
                fields=['name','package_name','destination'],
                order_by='creation desc', limit=50)

        total_revenue = 0
        try:
            result = frappe.db.sql(
                "SELECT COALESCE(SUM(total_amount),0) FROM `tabBooking`")
            total_revenue = float(result[0][0]) if result else 0
        except Exception:
            pass

        return {
            'leads': leads,
            'bookings': bookings,
            'packages': packages,
            'customers': [l for l in leads if l.get('status') in ['Booked','Customer']],
            'team': [],
            'stats': {
                'total_leads': len(leads),
                'total_bookings': len(bookings),
                'total_revenue': total_revenue,
                'open_leads': len([l for l in leads if l.get('status') == 'Open'])
            }
        }
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), 'get_founder_data Error')
        frappe.throw(str(e))

@frappe.whitelist()
def create_lead(**kwargs):
    try:
        doc = frappe.get_doc({'doctype': 'Travel Lead'})
        for k, v in kwargs.items():
            if hasattr(doc, k):
                setattr(doc, k, v)
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
        return {'success': True, 'name': doc.name}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), 'create_lead Error')
        return {'success': False, 'error': str(e)}

@frappe.whitelist()
def update_lead(**kwargs):
    try:
        name = kwargs.pop('lead_id', None) or kwargs.pop('name', None)
        if name and frappe.db.exists('Travel Lead', name):
            doc = frappe.get_doc('Travel Lead', name)
            for k, v in kwargs.items():
                if hasattr(doc, k):
                    setattr(doc, k, v)
            doc.save(ignore_permissions=True)
            frappe.db.commit()
            return {'success': True, 'name': doc.name}
        return create_lead(**kwargs)
    except Exception as e:
        return {'success': False, 'error': str(e)}

@frappe.whitelist()
def create_booking(**kwargs):
    try:
        doc = frappe.get_doc({'doctype': 'Booking'})
        for k, v in kwargs.items():
            if hasattr(doc, k):
                setattr(doc, k, v)
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
        return {'success': True, 'name': doc.name}
    except Exception as e:
        return {'success': False, 'error': str(e)}

@frappe.whitelist()
def save_package(**kwargs):
    try:
        pkg_id = kwargs.pop('pkg_id', None)
        if pkg_id and frappe.db.exists('Tour Package', pkg_id):
            doc = frappe.get_doc('Tour Package', pkg_id)
        else:
            doc = frappe.get_doc({'doctype': 'Tour Package'})
        for k, v in kwargs.items():
            if hasattr(doc, k):
                setattr(doc, k, v)
        if doc.is_new():
            doc.insert(ignore_permissions=True)
        else:
            doc.save(ignore_permissions=True)
        frappe.db.commit()
        return {'success': True, 'name': doc.name}
    except Exception as e:
        return {'success': False, 'error': str(e)}

@frappe.whitelist()
def update_booking_status(booking_name, status):
    try:
        frappe.db.set_value('Booking', booking_name, 'status', status)
        frappe.db.commit()
        return {'success': True}
    except Exception as e:
        return {'success': False, 'error': str(e)}

@frappe.whitelist()
def record_payment(**kwargs):
    frappe.db.commit()
    return {'success': True}

@frappe.whitelist()
def update_visa_status(**kwargs):
    frappe.db.commit()
    return {'success': True}

@frappe.whitelist()
def delete_record(doctype, record_name):
    try:
        frappe.delete_doc(doctype, record_name, ignore_permissions=True)
        frappe.db.commit()
        return {'success': True}
    except Exception as e:
        return {'success': False, 'error': str(e)}
