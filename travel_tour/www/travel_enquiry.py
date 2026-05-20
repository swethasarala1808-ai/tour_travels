"""
travel_tour/www/travel_enquiry.py
Customer Portal — reads real Travel Tour doctypes
"""
import frappe
from frappe.utils import flt, cint


def get_context(context):
    context.no_cache = 1
    context.show_sidebar = False
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/my_portal"
        raise frappe.Redirect
    # Verify a lead exists for this user
    mobile = frappe.db.get_value("User", frappe.session.user, "mobile_no") or ""
    email  = frappe.session.user
    lead = (
        frappe.db.get_value("Travel Lead", {"email_id": email}, "name") or
        (frappe.db.get_value("Travel Lead", {"mobile_no": mobile}, "name") if mobile else None)
    )
    if not lead:
        frappe.local.flags.redirect_location = "/my_portal"
        raise frappe.Redirect


@frappe.whitelist()
def get_portal_data():
    """Return all portal data for the logged-in customer."""
    if frappe.session.user == "Guest":
        frappe.throw("Please login.", frappe.AuthenticationError)

    email  = frappe.session.user
    mobile = frappe.db.get_value("User", frappe.session.user, "mobile_no") or ""

    # Find lead by email or mobile
    lead_name = (
        frappe.db.get_value("Travel Lead", {"email_id": email}, "name") or
        (frappe.db.get_value("Travel Lead", {"mobile_no": mobile}, "name") if mobile else None)
    )

    if not lead_name:
        return None

    # Get lead with all available fields
    meta = frappe.get_meta("Travel Lead")
    real_fields = {f.fieldname for f in meta.fields}
    real_fields.update({"name", "status", "creation"})

    want = ["name", "status", "creation",
            "lead_name", "full_name", "mobile_no", "phone", "email_id",
            "interested_destination", "destination", "tour_type_pref", "tour_type",
            "travel_month", "pax_count", "budget_per_person",
            "assigned_consultant", "lead_owner"]
    safe = [f for f in want if f in real_fields]

    lead = frappe.db.get_value("Travel Lead", lead_name, safe, as_dict=True)

    # Normalize
    lead["lead_name"]              = lead.get("lead_name") or lead.get("full_name") or lead_name
    lead["mobile"]                 = lead.get("mobile_no") or lead.get("phone") or mobile
    lead["email"]                  = lead.get("email_id") or email
    lead["interested_destination"] = lead.get("interested_destination") or lead.get("destination") or ""
    lead["tour_type_pref"]         = lead.get("tour_type_pref") or lead.get("tour_type") or ""
    lead["assigned_consultant"]    = lead.get("assigned_consultant") or lead.get("lead_owner") or ""
    lead.setdefault("travel_month", "")
    lead.setdefault("pax_count", 0)
    lead.setdefault("budget_per_person", 0)

    # Get bookings
    bookings = _get_customer_bookings(lead["lead_name"], lead_name)

    return {"lead": lead, "bookings": bookings}


def _get_customer_bookings(customer_name, lead_name):
    """Fetch bookings for this customer."""
    bk_meta = frappe.get_meta("Booking")
    real_fields = {f.fieldname for f in bk_meta.fields}
    real_fields.update({"name", "creation", "docstatus"})

    want = [
        "name", "creation", "departure_date", "return_date",
        "tour_package", "booking_status", "status",
        "total_pax", "pax_count", "adult_pax", "child_pax",
        "grand_total", "total_amount", "advance_paid", "paid_amount",
        "balance_due", "balance_due_date",
        "payment_status", "room_category",
        "destination", "sales_consultant", "special_requests",
        "customer", "lead", "travel_lead",
        # financials
        "base_amount", "addons_total", "gst_amount", "tcs_amount", "discount_amount",
    ]
    safe = [f for f in want if f in real_fields]

    # Try customer name match OR lead match
    filters = [
        ["docstatus", "!=", 2],
        ["customer", "in", [customer_name, lead_name, ""]],
    ]

    bookings = frappe.get_all("Booking", fields=safe, order_by="creation desc", limit=100,
                               filters={"docstatus": ["!=", 2]})

    # Filter to this customer
    my_bks = [
        b for b in bookings
        if (b.get("customer") or "").lower() in [customer_name.lower(), lead_name.lower()]
        or b.get("lead") == lead_name
        or b.get("travel_lead") == lead_name
    ]

    if not my_bks:
        my_bks = bookings  # if no match, show all (single-customer demo)

    pax_meta = frappe.get_meta("Booking Pax")
    pax_real = {f.fieldname for f in pax_meta.fields}
    pax_want = ["pax_name", "pax_type", "age", "gender", "id_type",
                "id_number", "passport_expiry", "nationality", "visa_status"]
    pax_safe = [f for f in pax_want if f in pax_real]

    for b in my_bks:
        # Normalize
        b.setdefault("booking_status", b.get("status") or "Draft")
        b.setdefault("total_pax", cint(b.get("pax_count") or b.get("adult_pax") or 0))
        b.setdefault("grand_total", flt(b.get("total_amount") or 0))
        b.setdefault("advance_paid", flt(b.get("paid_amount") or 0))
        b.setdefault("balance_due",
            flt(b.get("grand_total", 0)) - flt(b.get("advance_paid", 0)))
        b.setdefault("payment_status",
            "Paid" if b.get("balance_due", 1) <= 0 else "Partial")
        b.setdefault("base_amount", b.get("grand_total") or 0)
        b.setdefault("addons_total", 0)
        b.setdefault("gst_amount", 0)
        b.setdefault("tcs_amount", 0)
        b.setdefault("discount_amount", 0)

        b["pax_details"] = frappe.get_all(
            "Booking Pax",
            filters={"parent": b["name"]},
            fields=pax_safe or ["name"],
        )

        # Itinerary from Tour Package
        b["itinerary_days"] = []
        if b.get("tour_package"):
            itin_meta = frappe.get_meta("Itinerary Day")
            itin_real = {f.fieldname for f in itin_meta.fields}
            itin_want = ["day_number", "day_title", "morning", "afternoon", "evening", "hotel", "description"]
            itin_safe = [f for f in itin_want if f in itin_real]
            if itin_safe:
                b["itinerary_days"] = frappe.get_all(
                    "Itinerary Day",
                    filters={"parent": b["tour_package"]},
                    fields=itin_safe,
                    order_by="day_number asc",
                )

    return my_bks


@frappe.whitelist()
def update_lead_enquiry(**kwargs):
    """Update or create a new lead for the logged-in customer."""
    if frappe.session.user == "Guest":
        return {"success": False, "error": "Not logged in."}

    email  = frappe.session.user
    mobile = frappe.db.get_value("User", frappe.session.user, "mobile_no") or ""

    lead_name = (
        frappe.db.get_value("Travel Lead", {"email_id": email}, "name") or
        (frappe.db.get_value("Travel Lead", {"mobile_no": mobile}, "name") if mobile else None)
    )

    if not lead_name:
        return {"success": False, "error": "No account found."}

    doc = frappe.get_doc("Travel Lead", lead_name)
    meta = frappe.get_meta("Travel Lead")
    real_fields = {f.fieldname for f in meta.fields}

    mapping = {
        "destination":    ["interested_destination", "destination"],
        "tour_type":      ["tour_type_pref", "tour_type"],
        "travel_month":   ["travel_month"],
        "pax_count":      ["pax_count"],
        "budget":         ["budget_per_person", "budget"],
    }

    for k, candidates in mapping.items():
        val = kwargs.get(k)
        if val is None:
            continue
        for c in candidates:
            if c in real_fields:
                setattr(doc, c, val)
                break

    if kwargs.get("notes"):
        doc.add_comment("Comment", text=f"Portal enquiry: {kwargs['notes']}")

    try:
        doc.flags.ignore_permissions = True
        doc.save()
        frappe.db.commit()
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def update_profile(**kwargs):
    """Update customer profile."""
    if frappe.session.user == "Guest":
        return {"success": False}

    email = frappe.session.user
    mobile = frappe.db.get_value("User", frappe.session.user, "mobile_no") or ""
    lead_name = (
        frappe.db.get_value("Travel Lead", {"email_id": email}, "name") or
        (frappe.db.get_value("Travel Lead", {"mobile_no": mobile}, "name") if mobile else None)
    )
    if not lead_name:
        return {"success": False, "error": "Account not found."}

    doc = frappe.get_doc("Travel Lead", lead_name)
    meta = frappe.get_meta("Travel Lead")
    real_fields = {f.fieldname for f in meta.fields}

    mapping = {
        "lead_name":              ["lead_name", "full_name"],
        "email":                  ["email_id"],
        "tour_type_pref":         ["tour_type_pref", "tour_type"],
        "interested_destination": ["interested_destination", "destination"],
    }

    for k, candidates in mapping.items():
        val = kwargs.get(k)
        if val is None:
            continue
        for c in candidates:
            if c in real_fields:
                setattr(doc, c, val)
                break

    try:
        doc.flags.ignore_permissions = True
        doc.save()
        frappe.db.commit()
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def create_payment_link(booking_name):
    """Generate Razorpay payment link (stub — integrate your gateway)."""
    if frappe.session.user == "Guest":
        return {"success": False}
    # Stub: return a UPI deep-link or contact message
    doc = frappe.db.get_value("Booking", booking_name, ["balance_due", "grand_total"], as_dict=True)
    if not doc:
        return {"success": False, "error": "Booking not found."}
    if flt(doc.get("balance_due", 0)) <= 0:
        return {"success": False, "error": "No balance due."}
    try:
        settings = frappe.get_single("Travel Tour Settings")
        rzp_key = getattr(settings, "razorpay_key_id", None)
        if rzp_key:
            # Real integration placeholder
            return {"success": True, "url": f"https://rzp.io/l/{booking_name}"}
    except Exception:
        pass
    return {"success": False, "error": "Payment gateway not configured. Please contact us."}
