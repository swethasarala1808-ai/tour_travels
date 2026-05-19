import frappe
from frappe import _


# ─────────────────────────────────────────────────────────────────
# PUBLIC: Submit Enquiry (no login required)
# ─────────────────────────────────────────────────────────────────
@frappe.whitelist(allow_guest=True)
def submit_enquiry(
    full_name,
    mobile_no,
    email_id,
    pax_count=1,
    suggested_package=None,
    preferred_month=None,
    interest_tags=None,
    message=None,
    source="Website"
):
    """Create a Travel Lead from the public enquiry form."""

    # Basic validation
    if not full_name or not mobile_no or not email_id:
        frappe.throw(_("Name, mobile, and email are required."))

    if not frappe.utils.validate_email_address(email_id):
        frappe.throw(_("Please provide a valid email address."))

    # Build lead and set all fields
    lead = frappe.new_doc("Travel Lead")
    lead.full_name      = full_name
    lead.mobile_no      = mobile_no
    lead.email_id       = email_id
    lead.pax_count      = int(pax_count) if pax_count else 1
    lead.source         = source
    lead.status         = "Open"
    lead.preferred_month = preferred_month or ""
    lead.interest_tags   = interest_tags or ""

    if suggested_package:
        # Validate package exists
        if frappe.db.exists("Tour Package", suggested_package):
            lead.suggested_package = suggested_package

    # Store extra info in a custom remarks-style field if it exists,
    # otherwise just proceed (graceful degradation)
    notes_parts = []
    if message:
        notes_parts.append(f"Message: {message}")
    if notes_parts:
        try:
            lead.remarks = "\n".join(notes_parts)
        except Exception:
            pass

    try:
        lead.insert(ignore_permissions=True)
        frappe.db.commit()
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Enquiry Submission Error")
        frappe.throw(_("Could not save your enquiry. Please try again."))

    return {"status": "success", "lead_id": lead.name, "name": full_name}


# ─────────────────────────────────────────────────────────────────
# PRIVATE: Get Package Itinerary (logged-in)
# ─────────────────────────────────────────────────────────────────
@frappe.whitelist()
def get_package_itinerary(package):
    """Return itinerary days for a tour package."""
    if not package:
        return []

    if not frappe.db.exists("Tour Package", package):
        return []

    days = frappe.get_all(
        "Itinerary Day",
        filters={"parent": package, "parenttype": "Tour Package"},
        fields=["day_number", "title", "description", "meals"],
        order_by="day_number asc"
    )
    return days


# ─────────────────────────────────────────────────────────────────
# PRIVATE: Update Passport Details from Portal
# ─────────────────────────────────────────────────────────────────
@frappe.whitelist()
def update_passport_details(visa_id, passport_number, passport_expiry):
    """Allow a logged-in customer to update their passport on a visa application."""
    if frappe.session.user == "Guest":
        frappe.throw(_("You must be logged in."), frappe.AuthenticationError)

    if not visa_id:
        frappe.throw(_("Visa ID is required."))

    # Ensure this visa belongs to the requesting customer
    visa = frappe.get_doc("Visa Application", visa_id)
    booking = frappe.get_doc("Booking", visa.booking)

    customer_name = _get_customer_for_user(frappe.session.user)
    if not customer_name or booking.customer != customer_name:
        frappe.throw(_("Unauthorised access."), frappe.PermissionError)

    # Only allow updates while pending
    if visa.status not in ("Pending Documents", "Documents Collected"):
        frappe.throw(_("Passport details cannot be updated in the current visa status."))

    frappe.db.set_value("Visa Application", visa_id, {
        "passport_number": passport_number,
        "passport_expiry": passport_expiry
    })
    frappe.db.commit()
    return "ok"


# ─────────────────────────────────────────────────────────────────
# PRIVATE: Get customer linked to current user
# ─────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────
# HOOK: has_website_permission for Booking DocType
# ─────────────────────────────────────────────────────────────────
def has_booking_permission(doc, ptype="read", user=None, verbose=False):
    """Ensure users can only see their own bookings on the web."""
    if not user:
        user = frappe.session.user
    if user == "Guest":
        return False
    customer = _get_customer_for_user(user)
    if not customer:
        return False
    return doc.customer == customer


def _get_customer_for_user(user_email):
    """Returns customer name linked to the portal user, or None."""
    customer = frappe.db.get_value(
        "Customer",
        {"email_id": user_email},
        "name"
    )
    if customer:
        return customer

    # Fallback: check Contact→Customer link
    contact = frappe.db.sql("""
        SELECT dl.link_name
        FROM `tabContact Email` ce
        JOIN `tabDynamic Link` dl ON dl.parent = ce.parent
        WHERE ce.email_id = %s
          AND dl.link_doctype = 'Customer'
        LIMIT 1
    """, user_email, as_dict=True)

    if contact:
        return contact[0].link_name

    return None


# ─────────────────────────────────────────────────────────────────
# PRIVATE: Get portal summary (for AJAX refresh)
# ─────────────────────────────────────────────────────────────────
@frappe.whitelist()
def get_portal_summary():
    """Returns counts for the stat pills."""
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required."), frappe.AuthenticationError)

    customer_name = _get_customer_for_user(frappe.session.user)
    if not customer_name:
        return {}

    today = frappe.utils.today()

    total  = frappe.db.count("Booking", {"customer": customer_name, "docstatus": ["!=", 2]})
    upcoming = frappe.db.count("Booking", {
        "customer": customer_name,
        "docstatus": ["!=", 2],
        "departure_date": [">=", today]
    })
    past = total - upcoming
    visas = frappe.db.sql("""
        SELECT COUNT(*) as cnt FROM `tabVisa Application` va
        JOIN `tabBooking` b ON b.name = va.booking
        WHERE b.customer = %s
    """, customer_name, as_dict=True)

    return {
        "total_bookings": total,
        "upcoming_trips": upcoming,
        "past_trips": past,
        "visa_applications": visas[0].cnt if visas else 0
    }
