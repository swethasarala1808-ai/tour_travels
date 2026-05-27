import frappe
import json
import requests
from frappe.utils import now_datetime, get_url


# ══════════════════════════════════════════════════════════════════════════
#  WHATSAPP HELPER — send message via Meta Cloud API
# ══════════════════════════════════════════════════════════════════════════
def _get_wa_config():
    """Get WhatsApp API config from Travel Tour Settings."""
    try:
        if frappe.db.exists('Travel Tour Settings', 'Travel Tour Settings'):
            s = frappe.get_doc('Travel Tour Settings', 'Travel Tour Settings')
            return {
                'api_key': getattr(s, 'whatsapp_api_key', '') or '',
                'phone_id': getattr(s, 'whatsapp_phone_id', '') or '',
                'enabled': bool(getattr(s, 'whatsapp_api_key', '')),
            }
    except Exception:
        pass
    return {'api_key': '', 'phone_id': '', 'enabled': False}


def _send_wa_message(mobile, message):
    """
    Send a WhatsApp message via Meta Cloud API.
    Falls back to logging if not configured.
    """
    # Normalize mobile
    mobile = str(mobile or '').strip().replace('+', '').replace(' ', '').replace('-', '')
    if not mobile:
        return False
    if not mobile.startswith('91') and len(mobile) == 10:
        mobile = '91' + mobile

    cfg = _get_wa_config()
    if not cfg['enabled']:
        # Log the message instead of sending
        frappe.log_error(
            f"[WhatsApp] To: +{mobile}\n{message}",
            "WhatsApp Message (not sent - configure API key)"
        )
        return True  # Return True so workflow continues

    url = f"https://graph.facebook.com/v19.0/{cfg['phone_id']}/messages"
    headers = {
        'Authorization': f"Bearer {cfg['api_key']}",
        'Content-Type': 'application/json'
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": mobile,
        "type": "text",
        "text": {"body": message}
    }
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=10)
        if r.status_code == 200:
            return True
        else:
            frappe.log_error(f"WhatsApp API error: {r.text}", "WhatsApp Send Failed")
            return False
    except Exception as e:
        frappe.log_error(str(e), "WhatsApp Send Exception")
        return False


# ══════════════════════════════════════════════════════════════════════════
#  MESSAGE TEMPLATES
# ══════════════════════════════════════════════════════════════════════════
def msg_lead_received(lead_name, full_name, package_name, preferred_month, pax_count):
    """Message sent to customer when their enquiry is received."""
    portal_url = f"{get_url()}/travel_enquiry"
    pkg = f" for *{package_name}*" if package_name else ""
    month = f" in *{preferred_month}*" if preferred_month else ""
    return (
        f"✈️ *Tour Travels — Enquiry Received*\n\n"
        f"Hi *{full_name}*! 👋\n\n"
        f"Thank you for your enquiry{pkg}{month} for {pax_count} traveller(s).\n\n"
        f"Our team will review your requirements and get back to you within 24 hours.\n\n"
        f"📱 Track your enquiry anytime at:\n{portal_url}\n\n"
        f"_Reference: {lead_name}_"
    )


def msg_lead_interested(lead_name, full_name, package_name, consultant_name, portal_url):
    """Message sent when lead status changes to Interested."""
    pkg = f"*{package_name}*" if package_name else "your trip"
    consultant = f"*{consultant_name}*" if consultant_name else "our team"
    return (
        f"✈️ *Tour Travels — Great News!*\n\n"
        f"Hi *{full_name}*! 🎉\n\n"
        f"We've reviewed your enquiry for {pkg}.\n\n"
        f"Your dedicated consultant {consultant} will reach out to you shortly with a customized travel proposal.\n\n"
        f"📱 View your profile:\n{portal_url}\n\n"
        f"_Ref: {lead_name}_"
    )


def msg_booking_confirmed(booking_name, full_name, package_name, departure_date,
                           total_pax, grand_total, payment_link, portal_url):
    """Message sent when booking is created/confirmed."""
    return (
        f"✅ *Tour Travels — Booking Confirmed!*\n\n"
        f"Hi *{full_name}*! 🎊\n\n"
        f"Your travel booking has been confirmed:\n\n"
        f"📋 *Booking ID:* {booking_name}\n"
        f"🗺️ *Package:* {package_name}\n"
        f"📅 *Departure:* {departure_date}\n"
        f"👥 *Travellers:* {total_pax}\n"
        f"💰 *Total Amount:* ₹{grand_total:,.0f}\n\n"
        f"💳 *Pay Now:*\n{payment_link}\n\n"
        f"📱 *Customer Portal:*\n{portal_url}\n\n"
        f"_Ref: {booking_name}_"
    )


def msg_payment_received(booking_name, full_name, amount, invoice_url, portal_url):
    """Message sent when payment is received."""
    return (
        f"💰 *Tour Travels — Payment Received!*\n\n"
        f"Hi *{full_name}*! 🙏\n\n"
        f"We've received your payment of *₹{amount:,.0f}* for booking {booking_name}.\n\n"
        f"🧾 *Download Invoice:*\n{invoice_url}\n\n"
        f"📱 *View Booking:*\n{portal_url}\n\n"
        f"Thank you for choosing Tour Travels! We look forward to making your trip memorable. ✈️"
    )


def msg_visa_update(full_name, applicant_name, visa_status, destination, portal_url):
    """Message sent when visa status changes."""
    status_emoji = {
        'Pending Documents': '📋', 'Documents Collected': '✅',
        'Submitted': '📨', 'Approved': '🎉', 'Rejected': '❌', 'Delivered': '📦'
    }.get(visa_status, '🛂')
    return (
        f"{status_emoji} *Tour Travels — Visa Update*\n\n"
        f"Hi *{full_name}*!\n\n"
        f"Visa status update for *{applicant_name}*:\n"
        f"🌍 Destination: *{destination}*\n"
        f"📊 Status: *{visa_status}*\n\n"
        f"📱 Track at:\n{portal_url}\n"
    )


def msg_departure_reminder(full_name, booking_name, package_name, departure_date, days_left):
    """Departure reminder message."""
    return (
        f"🛫 *Tour Travels — Departure Reminder*\n\n"
        f"Hi *{full_name}*! ⏰\n\n"
        f"Your trip is in *{days_left} day(s)*!\n\n"
        f"📋 Booking: {booking_name}\n"
        f"🗺️ Package: {package_name}\n"
        f"📅 Departure: *{departure_date}*\n\n"
        f"Please ensure you have all documents ready.\n"
        f"Have a wonderful journey! ✈️🌍"
    )


# ══════════════════════════════════════════════════════════════════════════
#  API ENDPOINTS — called from frappe hooks / frontend
# ══════════════════════════════════════════════════════════════════════════
@frappe.whitelist()
def send_enquiry_confirmation(lead_name):
    """Send WhatsApp confirmation when a new lead is created."""
    try:
        lead = frappe.get_doc('Travel Lead', lead_name)
        mobile = lead.mobile_no
        if not mobile:
            return {'success': False, 'error': 'No mobile number'}

        pkg_name = ''
        if lead.suggested_package:
            pkg_name = frappe.db.get_value('Tour Package',
                lead.suggested_package, 'package_name') or lead.suggested_package

        msg = msg_lead_received(
            lead_name=lead.name,
            full_name=lead.full_name or 'Customer',
            package_name=pkg_name,
            preferred_month=lead.preferred_month or '',
            pax_count=lead.pax_count or 1
        )
        ok = _send_wa_message(mobile, msg)
        if ok:
            _log_wa_activity(lead_name, 'Travel Lead', msg, mobile)
        return {'success': ok}
    except Exception as e:
        return {'success': False, 'error': str(e)}


@frappe.whitelist()
def send_lead_status_update(lead_name):
    """Send WhatsApp when lead status changes."""
    try:
        lead = frappe.get_doc('Travel Lead', lead_name)
        mobile = lead.mobile_no
        if not mobile:
            return {'success': False, 'error': 'No mobile number'}

        portal_url = f"{get_url()}/travel_enquiry"
        pkg_name = ''
        if lead.suggested_package:
            pkg_name = frappe.db.get_value('Tour Package',
                lead.suggested_package, 'package_name') or ''
        consultant_name = ''
        if lead.assigned_consultant:
            consultant_name = frappe.db.get_value('User',
                lead.assigned_consultant, 'full_name') or ''

        msg = msg_lead_interested(
            lead_name=lead.name,
            full_name=lead.full_name or 'Customer',
            package_name=pkg_name,
            consultant_name=consultant_name,
            portal_url=portal_url
        )
        ok = _send_wa_message(mobile, msg)
        if ok:
            _log_wa_activity(lead_name, 'Travel Lead', msg, mobile)
        return {'success': ok}
    except Exception as e:
        return {'success': False, 'error': str(e)}


@frappe.whitelist()
def send_booking_confirmation(booking_name):
    """Send WhatsApp booking confirmation with payment link."""
    try:
        bk = frappe.get_doc('Booking', booking_name)
        mobile = bk.customer_mobile
        if not mobile and bk.customer:
            mobile = frappe.db.get_value('Customer', bk.customer, 'mobile_no') or ''
        if not mobile:
            return {'success': False, 'error': 'No mobile number'}

        full_name = 'Customer'
        if bk.customer:
            full_name = frappe.db.get_value('Customer', bk.customer, 'customer_name') or 'Customer'

        pkg_name = bk.tour_package
        if bk.tour_package:
            pkg_name = frappe.db.get_value('Tour Package',
                bk.tour_package, 'package_name') or bk.tour_package

        portal_url = f"{get_url()}/travel_enquiry"
        payment_link = _create_razorpay_link(booking_name, bk.grand_total, full_name, mobile)

        msg = msg_booking_confirmed(
            booking_name=bk.name,
            full_name=full_name,
            package_name=pkg_name,
            departure_date=str(bk.departure_date or '—'),
            total_pax=bk.total_pax or 0,
            grand_total=bk.grand_total or 0,
            payment_link=payment_link or f"{portal_url}#payments",
            portal_url=portal_url
        )
        ok = _send_wa_message(mobile, msg)
        if ok:
            _log_wa_activity(booking_name, 'Booking', msg, mobile)
        return {'success': ok, 'payment_link': payment_link}
    except Exception as e:
        return {'success': False, 'error': str(e)}


@frappe.whitelist()
def send_visa_status_update(visa_name):
    """Send WhatsApp when visa status changes."""
    try:
        visa = frappe.get_doc('Visa Application', visa_name)
        mobile = ''
        full_name = 'Customer'
        if visa.booking:
            bk = frappe.get_doc('Booking', visa.booking)
            mobile = bk.customer_mobile or ''
            if bk.customer:
                full_name = frappe.db.get_value('Customer', bk.customer, 'customer_name') or 'Customer'
        if not mobile:
            return {'success': False, 'error': 'No mobile'}

        portal_url = f"{get_url()}/travel_enquiry"
        msg = msg_visa_update(
            full_name=full_name,
            applicant_name=visa.applicant_name or '—',
            visa_status=visa.status or '—',
            destination=visa.destination_country or '—',
            portal_url=portal_url
        )
        ok = _send_wa_message(mobile, msg)
        return {'success': ok}
    except Exception as e:
        return {'success': False, 'error': str(e)}


@frappe.whitelist()
def send_manual_message(mobile, message):
    """Send a custom WhatsApp message from founder dashboard."""
    if frappe.session.user == 'Guest':
        frappe.throw("Login required")
    ok = _send_wa_message(mobile, message)
    return {'success': ok}


# ══════════════════════════════════════════════════════════════════════════
#  RAZORPAY PAYMENT LINK
# ══════════════════════════════════════════════════════════════════════════
def _create_razorpay_link(booking_name, amount, customer_name, mobile):
    """Create Razorpay payment link and return URL."""
    try:
        settings = frappe.get_doc('Travel Tour Settings', 'Travel Tour Settings')
        key_id = getattr(settings, 'razorpay_key_id', '') or ''
        key_secret = getattr(settings, 'razorpay_key_secret', '') or ''

        if not key_id or not key_secret:
            # Return a portal payment page if Razorpay not configured
            return f"{get_url()}/travel_enquiry#pay-{booking_name}"

        import base64
        auth = base64.b64encode(f"{key_id}:{key_secret}".encode()).decode()
        payload = {
            "amount": int(float(amount or 0) * 100),  # paise
            "currency": "INR",
            "description": f"Tour Booking: {booking_name}",
            "customer": {
                "name": customer_name,
                "contact": f"+91{str(mobile).replace('+91','').replace(' ','')}"
            },
            "notify": {"sms": False, "email": False},
            "reminder_enable": True,
            "notes": {"booking_id": booking_name},
            "callback_url": f"{get_url()}/api/method/travel_tour.api.whatsapp.razorpay_callback",
            "callback_method": "get"
        }
        r = requests.post(
            "https://api.razorpay.com/v1/payment_links",
            headers={"Authorization": f"Basic {auth}", "Content-Type": "application/json"},
            json=payload, timeout=10
        )
        if r.status_code == 200:
            return r.json().get('short_url', '')
    except Exception as e:
        frappe.log_error(str(e), "Razorpay Link Creation Failed")
    return ''


@frappe.whitelist(allow_guest=True)
def razorpay_callback(**kwargs):
    """Handle Razorpay payment callback."""
    try:
        payment_id = kwargs.get('razorpay_payment_id', '')
        link_id = kwargs.get('razorpay_payment_link_id', '')
        status = kwargs.get('razorpay_payment_link_status', '')

        if status == 'paid' and payment_id:
            # Find booking from notes
            booking_name = kwargs.get('razorpay_payment_link_reference_id', '')
            if booking_name and frappe.db.exists('Booking', booking_name):
                # Log payment
                frappe.log_error(
                    f"Payment received: {payment_id} for {booking_name}",
                    "Razorpay Payment"
                )
                # Send WhatsApp confirmation
                bk = frappe.get_doc('Booking', booking_name)
                mobile = bk.customer_mobile or ''
                full_name = 'Customer'
                if bk.customer:
                    full_name = frappe.db.get_value('Customer', bk.customer, 'customer_name') or 'Customer'
                    mobile = mobile or frappe.db.get_value('Customer', bk.customer, 'mobile_no') or ''

                invoice_url = f"{get_url()}/api/method/travel_tour.api.whatsapp.download_invoice?booking={booking_name}"
                portal_url = f"{get_url()}/travel_enquiry"
                msg = msg_payment_received(
                    booking_name=booking_name,
                    full_name=full_name,
                    amount=float(bk.grand_total or 0),
                    invoice_url=invoice_url,
                    portal_url=portal_url
                )
                if mobile:
                    _send_wa_message(mobile, msg)

        # Redirect to portal
        frappe.local.flags.redirect_location = '/travel_enquiry?payment=success'
        raise frappe.Redirect
    except frappe.Redirect:
        raise
    except Exception as e:
        frappe.log_error(str(e), "Razorpay Callback Error")
        frappe.local.flags.redirect_location = '/travel_enquiry?payment=error'
        raise frappe.Redirect


# ══════════════════════════════════════════════════════════════════════════
#  INVOICE DOWNLOAD
# ══════════════════════════════════════════════════════════════════════════
@frappe.whitelist(allow_guest=True)
def download_invoice(booking=None):
    """Generate and return a simple HTML payment invoice."""
    if not booking or not frappe.db.exists('Booking', booking):
        frappe.throw("Booking not found")

    bk = frappe.get_doc('Booking', booking)
    full_name = 'Customer'
    mobile = bk.customer_mobile or ''
    if bk.customer:
        full_name = frappe.db.get_value('Customer', bk.customer, 'customer_name') or 'Customer'
        mobile = mobile or frappe.db.get_value('Customer', bk.customer, 'mobile_no') or ''

    pkg_name = bk.tour_package
    if bk.tour_package:
        pkg_name = frappe.db.get_value('Tour Package', bk.tour_package, 'package_name') or bk.tour_package

    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Invoice {bk.name}</title>
<style>
body{{font-family:Arial,sans-serif;max-width:700px;margin:40px auto;padding:20px;color:#333}}
.header{{background:#1a7a5e;color:#fff;padding:24px;border-radius:10px;margin-bottom:24px}}
.header h1{{margin:0;font-size:24px}}
.header p{{margin:6px 0 0;opacity:.8;font-size:13px}}
table{{width:100%;border-collapse:collapse;margin:16px 0}}
th{{background:#f4f6f8;text-align:left;padding:10px 12px;font-size:12px;color:#666;text-transform:uppercase;letter-spacing:.05em}}
td{{padding:10px 12px;border-bottom:1px solid #eee;font-size:14px}}
.total-row td{{font-weight:700;font-size:16px;background:#e8f5f1;color:#1a7a5e}}
.footer{{text-align:center;margin-top:32px;color:#999;font-size:12px}}
@media print{{body{{margin:0}}}}
</style></head>
<body>
<div class="header">
  <h1>✈️ Tour Travels</h1>
  <p>Booking Invoice · {bk.name}</p>
</div>
<h3>Customer Details</h3>
<table>
  <tr><th>Name</th><td>{full_name}</td><th>Mobile</th><td>{mobile}</td></tr>
  <tr><th>Booking ID</th><td>{bk.name}</td><th>Date</th><td>{str(bk.creation)[:10]}</td></tr>
</table>
<h3>Booking Details</h3>
<table>
  <tr><th>Tour Package</th><td colspan="3">{pkg_name}</td></tr>
  <tr><th>Departure Date</th><td>{str(bk.departure_date or '—')}</td><th>Total Pax</th><td>{bk.total_pax or 0}</td></tr>
</table>
<h3>Payment Summary</h3>
<table>
  <tr><th>Base Amount</th><td>₹{float(bk.base_amount or 0):,.2f}</td></tr>
  <tr><th>Discount</th><td>- ₹{float(bk.discount_amount or 0):,.2f}</td></tr>
  <tr><th>GST (5%)</th><td>₹{float(bk.gst_amount or 0):,.2f}</td></tr>
  <tr><th>TCS</th><td>₹{float(bk.tcs_amount or 0):,.2f}</td></tr>
  <tr class="total-row"><td>Grand Total</td><td>₹{float(bk.grand_total or 0):,.2f}</td></tr>
</table>
<div style="text-align:center;margin:24px 0">
  <button onclick="window.print()" style="background:#1a7a5e;color:#fff;border:none;padding:12px 28px;border-radius:8px;font-size:14px;cursor:pointer">🖨️ Print Invoice</button>
</div>
<div class="footer">
  <p>Thank you for choosing Tour Travels! ✈️</p>
  <p>This is a computer-generated invoice and does not require a signature.</p>
</div>
</body></html>"""

    frappe.local.response['type'] = 'page'
    frappe.local.response['html'] = html
    return html


# ══════════════════════════════════════════════════════════════════════════
#  ACTIVITY LOG HELPER
# ══════════════════════════════════════════════════════════════════════════
def _log_wa_activity(ref_name, ref_doctype, message, mobile):
    """Log WhatsApp message as a comment on the document."""
    try:
        frappe.get_doc({
            'doctype': 'Comment',
            'comment_type': 'Info',
            'reference_doctype': ref_doctype,
            'reference_name': ref_name,
            'content': f"📱 WhatsApp sent to +{mobile}:\n{message[:300]}",
        }).insert(ignore_permissions=True)
        frappe.db.commit()
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════════════
#  WORKFLOW AUTOMATION — called from founder dashboard
# ══════════════════════════════════════════════════════════════════════════
@frappe.whitelist()
def convert_lead_to_booking(lead_name, tour_package, departure_date, total_pax):
    """
    Full workflow: Lead → Customer → Booking → WhatsApp notification
    This is the core business flow for Tour Travels.
    """
    if frappe.session.user == 'Guest':
        frappe.throw("Login required")

    try:
        lead = frappe.get_doc('Travel Lead', lead_name)
        mobile = lead.mobile_no or ''
        full_name = lead.full_name or 'Customer'

        # Step 1: Get or create Customer
        customer_name = lead.customer
        if not customer_name:
            cg = frappe.db.sql(
                "SELECT name FROM `tabCustomer Group` WHERE is_group=0 LIMIT 1",
                as_list=True
            )
            cg = cg[0][0] if cg else 'Individual'
            ter = frappe.db.sql(
                "SELECT name FROM `tabTerritory` WHERE is_group=0 LIMIT 1",
                as_list=True
            )
            ter = ter[0][0] if ter else 'All Territories'

            # Check existing customer by mobile
            if mobile:
                customer_name = frappe.db.get_value('Customer',
                    {'mobile_no': ['in', [mobile, '+91'+mobile.replace('+91','')]]}, 'name')

            if not customer_name:
                cust = frappe.new_doc('Customer')
                cust.customer_name = full_name
                cust.customer_type = 'Individual'
                cust.customer_group = cg
                cust.territory = ter
                try:
                    cust.mobile_no = mobile
                except Exception:
                    pass
                cust.insert(ignore_permissions=True)
                frappe.db.commit()
                customer_name = cust.name

            # Link customer to lead
            frappe.db.set_value('Travel Lead', lead_name, 'customer', customer_name)
            frappe.db.commit()

        # Step 2: Update lead status to 'converted'
        frappe.db.set_value('Travel Lead', lead_name, 'status', 'converted')
        frappe.db.commit()

        # Step 3: Create Booking
        bk = frappe.new_doc('Booking')
        bk.customer = customer_name
        bk.customer_mobile = mobile
        bk.tour_package = tour_package
        bk.departure_date = departure_date
        bk.total_pax = int(total_pax or 1)
        bk.save(ignore_permissions=True)
        frappe.db.commit()

        # Step 4: Link booking to lead
        frappe.db.set_value('Travel Lead', lead_name, 'converted_booking', bk.name)
        frappe.db.commit()

        # Step 5: Send WhatsApp booking confirmation
        pkg_name = frappe.db.get_value('Tour Package', tour_package, 'package_name') or tour_package
        portal_url = f"{get_url()}/travel_enquiry"
        payment_link = _create_razorpay_link(bk.name, bk.grand_total, full_name, mobile)

        wa_msg = msg_booking_confirmed(
            booking_name=bk.name,
            full_name=full_name,
            package_name=pkg_name,
            departure_date=str(departure_date),
            total_pax=int(total_pax or 1),
            grand_total=float(bk.grand_total or 0),
            payment_link=payment_link or f"{portal_url}#payments",
            portal_url=portal_url
        )
        wa_ok = _send_wa_message(mobile, wa_msg)
        if wa_ok:
            _log_wa_activity(bk.name, 'Booking', wa_msg, mobile)

        return {
            'success': True,
            'booking_name': bk.name,
            'customer_name': customer_name,
            'grand_total': bk.grand_total,
            'payment_link': payment_link,
            'whatsapp_sent': wa_ok,
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "convert_lead_to_booking Error")
        return {'success': False, 'error': str(e)}
