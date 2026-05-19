# travel_tour/hooks.py

app_name        = 'travel_tour'
app_title       = 'Travel Tour'
app_publisher   = 'Your Company'
app_description = 'Travel, Tour & Visa Management for ERPNext'
app_version     = '2.0.0'
app_license     = 'MIT'
required_apps   = ['frappe', 'erpnext']

# ── DocType overrides ──────────────────────────────────────
override_doctype_class = {
    'Lead':         'travel_tour.overrides.lead.TravelLead',
    'Customer':     'travel_tour.overrides.customer.TravelCustomer',
    'Sales Invoice':'travel_tour.overrides.sales_invoice.TCSInvoice',
}

# ── Document events ────────────────────────────────────────
doc_events = {
    'Booking': {
        'on_submit': [
            'travel_tour.events.booking.on_submit',
            'travel_tour.events.booking.create_visa_applications',
            'travel_tour.events.booking.allocate_allotments',
            'travel_tour.events.booking.send_confirmation_whatsapp',
            'travel_tour.events.booking.create_run_sheet',
        ],
        'on_cancel': 'travel_tour.events.booking.on_cancel',
    },
    'Visa Application': {
        'on_update': 'travel_tour.events.visa_application.notify_status_change',
        'on_submit': 'travel_tour.events.visa_application.on_submit',
    },
    'Travel Lead': {
        'after_insert': [
            'travel_tour.events.travel_lead.assign_consultant',
            'travel_tour.events.travel_lead.send_ack_whatsapp',
        ],
    },
    'Supplier Contract': {
        'on_submit': 'travel_tour.events.supplier_contract.on_submit',
    },
}

# ── Scheduled tasks ────────────────────────────────────────
scheduler_events = {
    'daily': [
        'travel_tour.tasks.booking_tasks.balance_due_reminders',
        'travel_tour.tasks.booking_tasks.departure_reminders',
        'travel_tour.tasks.booking_tasks.post_trip_review_requests',
        'travel_tour.tasks.visa_tasks.document_collection_reminders',
        'travel_tour.tasks.visa_tasks.submission_deadline_alerts',
        'travel_tour.tasks.visa_tasks.passport_expiry_checks',
        'travel_tour.tasks.visa_tasks.insurance_expiry_alerts',
        'travel_tour.tasks.allotment_tasks.low_stock_alerts',
        'travel_tour.tasks.allotment_tasks.auto_release_allotments',
        'travel_tour.tasks.booking_tasks.supplier_payment_due_alerts',
        'travel_tour.tasks.booking_tasks.lead_followup_reminders',
    ],
    'weekly': [
        'travel_tour.tasks.booking_tasks.flag_slow_leads',
        'travel_tour.tasks.visa_tasks.visa_status_summary_to_ops',
    ],
    'monthly': [
        'travel_tour.tasks.report_tasks.monthly_booking_report_email',
        'travel_tour.tasks.report_tasks.monthly_visa_revenue_report',
    ],
}

# ── Fixtures ───────────────────────────────────────────────
fixtures = [
    {'dt': 'Role', 'filters': [['name', 'in', [
        'Travel Admin', 'Travel Consultant', 'Visa Officer',
        'Operations Manager', 'Finance Executive', 'Tour Guide',
    ]]]},
    {'dt': 'Workflow'},
    {'dt': 'Print Format'},
    {'dt': 'Custom Field'},
    {'dt': 'Property Setter'},
    {'dt': 'Visa Country Config'},
]

# ── Web Portal ─────────────────────────────────────────────
portal_menu_items = [
    {
        'title': 'My Travel Portal',
        'route': '/my-portal',
        'reference_doctype': 'Booking',
        'role': 'Customer',
    },
    {
        'title': 'Register Travel Interest',
        'route': '/travel-enquiry',
        'reference_doctype': '',
        'role': '',
    },
]

has_website_permission = {
    'Booking': 'travel_tour.api.portal.has_booking_permission',
}

# ── Workspace ───────────────────────────────────────────────
# Workspace is usually defined via JSON in doctype/workspace
