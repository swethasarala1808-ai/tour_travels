"""
travel_tour/www/travel_enquiry.py
Customer Portal — uses EXACT Travel Tour doctype field names.
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
    lead = _find_lead(frappe.session.user, mobile)
    if not lead:
        frappe.local.flags.redirect_location = "/my_portal"
        raise frappe.Redirect


def _find_lead(email, mobile=""):
    """Find Travel Lead by email or mobile."""
    try:
        r = frappe.db.get_value("Travel Lead", {"email_id": email}, "name")
        if r:
            return r
    except Exception:
        pass
    if mobile:
        try:
            r = frappe.db.get_value("Travel Lead", {"mobile_no": mobile}, "name")
            if r:
                return r
        except Exception:
            pass
    return None


@frappe.whitelist()
def get_portal_data():
    """Return all portal data for the logged-in customer."""
    if frappe.session.user == "Guest":
        frappe.throw("Please login.", frappe.AuthenticationError)

    email  = frappe.session.user
    mobile = frappe.db.get_value("User", frappe.session.user, "mobile_no") or ""

    lead_name = _find_lead(email, mobile)
    if not lead_name:
        return None

    # Get lead via raw SQL (uses exact field names)
    lead_row = frappe.db.sql(
        """SELECT name, full_name, email_id, mobile_no,
                  status, source, pax_count, preferred_month,
                  assigned_consultant, remarks, suggested_package,
                  converted_booking
           FROM `tabTravel Lead` WHERE name=%s""",
        lead_name, as_dict=True
    )
    if not lead_row:
        return None
    lead = lead_row[0]

    # Normalize for frontend
    lead["lead_name"]              = lead.get("full_name") or lead_name
    lead["mobile"]                 = lead.get("mobile_no") or mobile
    lead["email"]                  = lead.get("email_id") or email
    lead["interested_destination"] = ""
    lead["tour_type_pref"]         = ""
    lead["travel_month"]           = lead.get("preferred_month") or ""
    lead.setdefault("pax_count", 0)

    # Get bookings for this customer
    bookings = _get_bookings(lead["lead_name"], lead_name)

    return {"lead": lead, "bookings": bookings}


def _get_bookings(customer_name, lead_name):
    try:
        rows = frappe.db.sql("""
            SELECT name, customer, customer_mobile, tour_package,
                   departure_date, total_pax, sales_consultant,
                   base_amount, discount_amount, gst_amount,
                   tcs_amount, grand_total, docstatus, creation
            FROM `tabBooking`
            WHERE docstatus != 2
              AND (customer = %s OR customer = %s)
            ORDER BY creation DESC
            LIMIT 100
        """, (customer_name, lead_name), as_dict=True)
    except Exception:
        rows = []

    result = []
    for b in rows:
        grand   = flt(b.get("grand_total") or 0)
        advance = _get_advance(b["name"])
        balance = max(0, grand - advance)
        ds      = cint(b.get("docstatus", 0))
        status  = {0: "Draft", 1: "Confirmed", 2: "Cancelled"}.get(ds, "Draft")

        # Pax details
        pax = []
        try:
            pax = frappe.db.sql("""
                SELECT pax_name, pax_age, pax_gender,
                       passport_number, passport_expiry
                FROM `tabBooking Pax`
                WHERE parent=%s
            """, b["name"], as_dict=True)
            for p in pax:
                p["id_number"]   = p.get("passport_number") or ""
                p["pax_type"]    = "Adult"
                p["visa_status"] = "Not Applied"
        except Exception:
            pax = []

        # Itinerary
        itinerary = []
        if b.get("tour_package"):
            try:
                itinerary = frappe.db.sql("""
                    SELECT day_number, title as day_title,
                           morning, afternoon, evening, hotel_name as hotel
                    FROM `tabItinerary Day`
                    WHERE parent=%s ORDER BY day_number ASC
                """, b["tour_package"], as_dict=True)
            except Exception:
                itinerary = []

        # Visa applications
        visa_status = "Not Applied"
        try:
            va = frappe.db.get_value(
                "Visa Application",
                {"booking": b["name"]},
                "status"
            )
            if va:
                visa_status = va
        except Exception:
            pass

        result.append({
            "name":             b["name"],
            "customer":         b.get("customer") or customer_name,
            "tour_package":     b.get("tour_package") or "",
            "departure_date":   str(b.get("departure_date") or ""),
            "return_date":      "",
            "total_pax":        cint(b.get("total_pax") or 0),
            "adult_pax":        cint(b.get("total_pax") or 0),
            "child_pax":        0,
            "room_category":    "",
            "base_amount":      flt(b.get("base_amount") or grand),
            "addons_total":     0,
            "gst_amount":       flt(b.get("gst_amount") or 0),
            "tcs_amount":       flt(b.get("tcs_amount") or 0),
            "discount_amount":  flt(b.get("discount_amount") or 0),
            "grand_total":      grand,
            "advance_paid":     advance,
            "balance_due":      balance,
            "balance_due_date": "",
            "payment_status":   "Paid" if balance <= 0 else "Partial",
            "booking_status":   status,
            "sales_consultant": b.get("sales_consultant") or "",
            "special_requests": "",
            "destination":      _pkg_dest(b.get("tour_package")),
            "creation":         str(b.get("creation") or ""),
            "pax_details":      pax,
            "itinerary_days":   itinerary,
            "visa_status":      visa_status,
        })
    return result


def _get_advance(booking_name):
    try:
        r = frappe.db.sql("""
            SELECT COALESCE(SUM(per.allocated_amount), 0)
            FROM `tabPayment Entry Reference` per
            JOIN `tabPayment Entry` pe ON pe.name = per.parent
            WHERE per.reference_name = %s AND pe.docstatus = 1
        """, booking_name)
        return flt(r[0][0]) if r else 0
    except Exception:
        return 0


def _pkg_dest(pkg_name):
    if not pkg_name:
        return ""
    try:
        return frappe.db.get_value("Tour Package", pkg_name, "destination") or ""
    except Exception:
        return ""


@frappe.whitelist()
def update_lead_enquiry(**kwargs):
    if frappe.session.user == "Guest":
        return {"success": False, "error": "Not logged in."}
    email  = frappe.session.user
    mobile = frappe.db.get_value("User", frappe.session.user, "mobile_no") or ""
    lead_name = _find_lead(email, mobile)
    if not lead_name:
        return {"success": False, "error": "Account not found."}
    try:
        doc = frappe.get_doc("Travel Lead", lead_name)
        if kwargs.get("travel_month"):  doc.preferred_month = kwargs["travel_month"]
        if kwargs.get("pax_count"):     doc.pax_count       = cint(kwargs["pax_count"])
        if kwargs.get("notes"):
            doc.add_comment("Comment", text=f"Portal enquiry: {kwargs['notes']}")
        doc.flags.ignore_permissions = True
        doc.save()
        frappe.db.commit()
        return {"success": True}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "update_lead_enquiry")
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def update_profile(**kwargs):
    if frappe.session.user == "Guest":
        return {"success": False}
    email  = frappe.session.user
    mobile = frappe.db.get_value("User", frappe.session.user, "mobile_no") or ""
    lead_name = _find_lead(email, mobile)
    if not lead_name:
        return {"success": False}
    try:
        doc = frappe.get_doc("Travel Lead", lead_name)
        if kwargs.get("lead_name"):  doc.full_name = kwargs["lead_name"]
        if kwargs.get("email"):      doc.email_id  = kwargs["email"]
        doc.flags.ignore_permissions = True
        doc.save()
        frappe.db.commit()
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def create_payment_link(booking_name):
    if frappe.session.user == "Guest":
        return {"success": False}
    try:
        bal = frappe.db.get_value("Booking", booking_name, "grand_total") or 0
        if flt(bal) <= 0:
            return {"success": False, "error": "No balance due."}
        return {"success": False, "error": "Payment gateway not configured. Please contact us."}
    except Exception as e:
        return {"success": False, "error": str(e)}
