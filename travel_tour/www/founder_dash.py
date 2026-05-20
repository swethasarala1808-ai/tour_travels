import frappe

def get_context(context):
    if frappe.session.user == 'Guest':
        frappe.local.flags.redirect_location = '/login?redirect-to=/founder_dash'
        raise frappe.Redirect
    user_roles = frappe.get_roles(frappe.session.user)
    if not any(r in user_roles for r in ['System Manager', 'Administrator', 'Founder']):
        frappe.throw("Access denied", frappe.PermissionError)
    context.no_cache = 1

@frappe.whitelist()
def get_founder_data():
    if frappe.session.user == 'Guest':
        frappe.throw("Login required", frappe.AuthenticationError)

    leads_raw = frappe.get_all('Travel Lead',
        fields=['name','full_name','email_id','mobile_no','status','source',
                'suggested_package','pax_count','preferred_month','assigned_consultant','creation'],
        order_by='creation desc', limit=200)

    leads = [{'name':l.name,'lead_name':l.full_name or '','mobile':l.mobile_no or '',
              'email':l.email_id or '','status':l.status or 'New','source':l.source or '',
              'interested_destination':l.suggested_package or '','tour_type_pref':'',
              'travel_month':l.preferred_month or '','pax_count':l.pax_count or 0,
              'budget_per_person':0,'assigned_consultant':l.assigned_consultant or '',
              'creation':str(l.creation)[:10] if l.creation else ''} for l in leads_raw]

    bookings = []
    if frappe.db.table_exists('tabBooking'):
        bk_raw = frappe.get_all('Booking',
            fields=['name','travel_lead','tour_package','travel_date','status',
                    'total_amount','paid_amount','pax_count','creation'],
            order_by='creation desc', limit=200)
        for b in bk_raw:
            total = float(b.total_amount or 0)
            paid = float(b.paid_amount or 0)
            balance = total - paid
            lead_name = ''
            if b.travel_lead:
                lead_name = frappe.db.get_value('Travel Lead', b.travel_lead, 'full_name') or b.travel_lead
            bookings.append({'name':b.name,'customer':lead_name,'travel_lead':b.travel_lead or '',
                'tour_package':b.tour_package or '','departure_date':str(b.travel_date)[:10] if b.travel_date else '',
                'return_date':'','total_pax':b.pax_count or 0,'adult_pax':b.pax_count or 0,'child_pax':0,
                'grand_total':total,'advance_paid':paid,'balance_due':balance,
                'payment_status':'Paid' if balance<=0 else 'Partial' if paid>0 else 'Pending',
                'booking_status':b.status or 'Pending','sales_consultant':'',
                'destination':b.tour_package or '','creation':str(b.creation)[:10] if b.creation else '',
                'pax_details':[]})

    packages = []
    if frappe.db.table_exists('tabTour Package'):
        pkg_raw = frappe.get_all('Tour Package',
            fields=['name','package_name','destination','duration_days','base_price','status'],
            order_by='creation desc', limit=100)
        packages = [{'name':p.name,'package_name':p.package_name or p.name,
            'destination':p.destination or '','duration_days':p.duration_days or 0,
            'base_price':float(p.base_price or 0),'status':p.status or 'Active'} for p in pkg_raw]

    total_revenue=0; balance_due_total=0; active_bookings=0
    if frappe.db.table_exists('tabBooking'):
        try:
            r = frappe.db.sql("""SELECT COALESCE(SUM(total_amount),0) rev,
                COALESCE(SUM(total_amount-COALESCE(paid_amount,0)),0) bal,
                COUNT(CASE WHEN status IN ('Confirmed','Active') THEN 1 END) act
                FROM `tabBooking`""", as_dict=True)
            if r: total_revenue=float(r[0].rev or 0); balance_due_total=float(r[0].bal or 0); active_bookings=int(r[0].act or 0)
        except: pass

    open_leads = len([l for l in leads if l['status'] not in ['Converted','Lost','Closed']])
    departures_30d = len([b for b in bookings if b['booking_status']=='Confirmed' and b['departure_date']>=frappe.utils.today()])
    fu = frappe.db.get_value('User', frappe.session.user, ['full_name','first_name'], as_dict=True) or {}

    return {'leads':leads,'bookings':bookings,'packages':packages,
        'customers':[l for l in leads if l['status'] in ['Converted','Customer','Booked']],
        'team':[],'settings':{},
        'stats':{'total_revenue':total_revenue,'total_balance_due':balance_due_total,
            'active_bookings':active_bookings,'open_leads':open_leads,
            'lead_count':len(leads),'departures_30d':departures_30d},
        'founder':{'full_name':fu.get('full_name') or 'Founder',
            'first_name':fu.get('first_name') or 'Founder','email':frappe.session.user}}

@frappe.whitelist()
def create_lead(**kwargs):
    doc = frappe.get_doc({"doctype":"Travel Lead",
        "full_name":kwargs.get('lead_name') or kwargs.get('full_name',''),
        "email_id":kwargs.get('email',''),"mobile_no":kwargs.get('mobile',''),
        "status":kwargs.get('status','New'),"source":kwargs.get('source',''),
        "suggested_package":kwargs.get('interested_destination',''),
        "pax_count":int(kwargs.get('pax_count') or 0),
        "preferred_month":kwargs.get('travel_month',''),
        "assigned_consultant":kwargs.get('assigned_consultant','')})
    doc.flags.ignore_hooks = True
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return {'success':True,'name':doc.name}

@frappe.whitelist()
def update_lead(**kwargs):
    lead_id = kwargs.get('lead_id') or kwargs.get('name')
    if lead_id and frappe.db.exists('Travel Lead', lead_id):
        doc = frappe.get_doc('Travel Lead', lead_id)
        if kwargs.get('lead_name') or kwargs.get('full_name'): doc.full_name = kwargs.get('lead_name') or kwargs.get('full_name')
        if kwargs.get('email'):   doc.email_id = kwargs['email']
        if kwargs.get('mobile'):  doc.mobile_no = kwargs['mobile']
        if kwargs.get('status'):  doc.status = kwargs['status']
        if kwargs.get('interested_destination'): doc.suggested_package = kwargs['interested_destination']
        if kwargs.get('assigned_consultant'):    doc.assigned_consultant = kwargs['assigned_consultant']
        if kwargs.get('travel_month'):           doc.preferred_month = kwargs['travel_month']
        if kwargs.get('pax_count') is not None:  doc.pax_count = int(kwargs['pax_count'] or 0)
        doc.flags.ignore_hooks = True
        doc.save(ignore_permissions=True); frappe.db.commit()
        return {'success':True,'name':doc.name}
    return create_lead(**kwargs)

@frappe.whitelist()
def create_booking(**kwargs):
    if not frappe.db.table_exists('tabBooking'):
        return {'success':False,'error':'Booking module not available'}
    doc = frappe.get_doc({"doctype":"Booking",
        "travel_lead":kwargs.get('travel_lead',''),
        "tour_package":kwargs.get('tour_package',''),
        "travel_date":kwargs.get('departure_date') or kwargs.get('travel_date',''),
        "pax_count":int(kwargs.get('total_pax') or kwargs.get('pax_count') or 1),
        "total_amount":float(kwargs.get('grand_total') or kwargs.get('total_amount') or 0),
        "paid_amount":float(kwargs.get('advance_paid') or 0),
        "status":kwargs.get('booking_status') or kwargs.get('status','Pending')})
    doc.insert(ignore_permissions=True); frappe.db.commit()
    return {'success':True,'name':doc.name}

update_booking = create_booking

@frappe.whitelist()
def update_booking_status(booking_name, status):
    if frappe.db.exists('Booking', booking_name):
        frappe.db.set_value('Booking', booking_name, 'status', status)
        frappe.db.commit(); return {'success':True}
    return {'success':False,'error':'Not found'}

@frappe.whitelist()
def record_payment(**kwargs):
    bname = kwargs.get('booking_name')
    amount = float(kwargs.get('amount') or 0)
    if bname and frappe.db.exists('Booking', bname):
        paid = float(frappe.db.get_value('Booking', bname, 'paid_amount') or 0)
        frappe.db.set_value('Booking', bname, 'paid_amount', paid + amount)
        frappe.db.commit(); return {'success':True}
    return {'success':False,'error':'Not found'}

@frappe.whitelist()
def save_package(**kwargs):
    if not frappe.db.table_exists('tabTour Package'):
        return {'success':False,'error':'Not available'}
    pkg_id = kwargs.get('pkg_id') or kwargs.get('name')
    doc = frappe.get_doc('Tour Package', pkg_id) if pkg_id and frappe.db.exists('Tour Package', pkg_id) else frappe.new_doc('Tour Package')
    for k in ['package_name','destination','duration_days','base_price','status']:
        if kwargs.get(k) is not None: setattr(doc, k, kwargs[k])
    doc.save(ignore_permissions=True); frappe.db.commit()
    return {'success':True,'name':doc.name}

save_team_member = save_package

@frappe.whitelist()
def update_visa_status(booking_name, pax_name, visa_status):
    if frappe.db.table_exists('tabVisa Application'):
        visas = frappe.get_all('Visa Application',
            filters={'booking':booking_name,'pax_name':pax_name}, pluck='name')
        if visas:
            frappe.db.set_value('Visa Application', visas[0], 'status', visa_status)
            frappe.db.commit(); return {'success':True}
    return {'success':False,'error':'Not found'}

@frappe.whitelist()
def delete_record(doctype, record_name):
    if doctype not in ['Travel Lead','Booking','Tour Package','Visa Application']:
        return {'success':False,'error':'Not allowed'}
    if frappe.db.exists(doctype, record_name):
        frappe.delete_doc(doctype, record_name, ignore_permissions=True)
        frappe.db.commit(); return {'success':True}
    return {'success':False,'error':'Not found'}
