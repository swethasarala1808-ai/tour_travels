import frappe
from frappe.utils import now

def get_context(context):
    """Customer Portal — requires login. Shows bookings, visa, upcoming trips."""
    if frappe.session.user == 'Guest':
        frappe.local.flags.redirect_location = '/login?redirect-to=/my-portal'
        raise frappe.Redirect

    context.no_cache = 1

    # Find customer linked to this user
    customer = frappe.db.get_value(
        'Customer',
        {'email_id': frappe.session.user},
        ['name', 'customer_name', 'mobile_no', 'email_id'],
        as_dict=True
    )

    if not customer:
        # Try fallback by portal user link
        customer = frappe.db.get_value(
            'Contact',
            {'email_id': frappe.session.user, 'is_primary_contact': 1},
            ['customer'],
            as_dict=True
        )

    context.customer = customer

    if not customer:
        context.no_customer = True
        context.user_email = frappe.session.user
        context.user_name = frappe.db.get_value('User', frappe.session.user, 'full_name')
        return

    cname = customer.name

    # Active / upcoming bookings
    bookings = frappe.get_all(
        'Booking',
        filters={'customer': cname, 'docstatus': ['!=', 2]},
        fields=['name', 'tour_package', 'departure_date', 'total_pax',
                'grand_total', 'docstatus', 'creation'],
        order_by='departure_date asc'
    )

    today = frappe.utils.today()
    for b in bookings:
        b.status_label = 'Confirmed' if b.docstatus == 1 else 'Draft'
        b.is_upcoming = b.departure_date and str(b.departure_date) >= today
        b.is_past = b.departure_date and str(b.departure_date) < today

        # Load pax details
        b.pax_list = frappe.get_all(
            'Booking Pax',
            filters={'parent': b.name},
            fields=['pax_name', 'pax_age', 'pax_gender', 'passport_number', 'passport_expiry']
        )

        # Load addons
        b.addons_list = frappe.get_all(
            'Booking Addon',
            filters={'parent': b.name},
            fields=['addon_name', 'qty', 'amount']
        )

        # Package details
        if b.tour_package:
            pkg = frappe.db.get_value(
                'Tour Package',
                b.tour_package,
                ['package_name', 'tour_type', 'destination', 'duration_nights', 'duration_days', 'visa_required'],
                as_dict=True
            )
            b.package_info = pkg

    context.upcoming_bookings = [b for b in bookings if b.is_upcoming]
    context.past_bookings = [b for b in bookings if not b.is_upcoming]
    context.all_bookings = bookings

    # Visa applications
    booking_names = [b.name for b in bookings]
    visa_apps = []
    if booking_names:
        visa_apps = frappe.get_all(
            'Visa Application',
            filters={'booking': ['in', booking_names]},
            fields=['name', 'booking', 'applicant_name', 'visa_type', 'destination_country',
                    'departure_date', 'status', 'submission_deadline', 'all_docs_collected',
                    'passport_number', 'passport_expiry'],
            order_by='creation desc'
        )

    for v in visa_apps:
        v.status_class = {
            'Pending Documents': 'status-pending',
            'Documents Collected': 'status-collected',
            'Submitted': 'status-submitted',
            'Approved': 'status-approved',
            'Rejected': 'status-rejected',
            'Delivered': 'status-delivered'
        }.get(v.status, 'status-pending')

    context.visa_applications = visa_apps

    # Travel checklist / alerts for upcoming trips
    context.travel_alerts = build_travel_alerts(context.upcoming_bookings, visa_apps)


def build_travel_alerts(upcoming_bookings, visa_apps):
    """Build actionable items for the customer."""
    alerts = []
    today = frappe.utils.today()
    days_30 = frappe.utils.add_days(today, 30)

    for b in upcoming_bookings:
        dep = str(b.departure_date) if b.departure_date else ''
        if dep and dep <= str(days_30):
            days_left = (frappe.utils.getdate(dep) - frappe.utils.getdate(today)).days
            alerts.append({
                'type': 'trip_soon',
                'icon': '✈️',
                'title': f'Trip in {days_left} days!',
                'msg': f'Your {b.tour_package} is {days_left} days away. Ensure all documents are ready.',
                'booking': b.name,
                'level': 'warning' if days_left <= 7 else 'info'
            })

    for v in visa_apps:
        if v.status == 'Pending Documents':
            alerts.append({
                'type': 'visa_docs',
                'icon': '📄',
                'title': f'Documents Needed for {v.applicant_name}',
                'msg': f'Visa application for {v.destination_country or "your destination"} is waiting for documents.',
                'booking': v.booking,
                'level': 'warning'
            })
        if v.status == 'Approved':
            alerts.append({
                'type': 'visa_approved',
                'icon': '✅',
                'title': f'Visa Approved!',
                'msg': f'{v.applicant_name}\'s visa for {v.destination_country} has been approved.',
                'booking': v.booking,
                'level': 'success'
            })

    return alerts
