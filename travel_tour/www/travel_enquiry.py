"""
travel_tour/www/travel_enquiry.py
Customer Portal — Data APIs
"""
import frappe


def get_context(context):
    """Requires login — redirects guests to /my_portal."""
    context.no_cache = 1
    context.show_sidebar = False

    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/my_portal"
        raise frappe.Redirect

    mobile = frappe.db.get_value("User", frappe.session.user, "mobile_no")
    if not mobile:
        frappe.local.flags.redirect_location = "/my_portal"
        raise frappe.Redirect

    if not frappe.db.exists("Travel Lead", {"mobile": mobile}):
        frappe.local.flags.redirect_location = "/my_portal"
        raise frappe.Redirect


# ──────────────────────────────────────────────────────────────────
# MAIN DATA LOADER
# ──────────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_portal_data():
    """Fetch all portal data for the logged-in customer."""
    if frappe.session.user == "Guest":
        return None

    mobile = frappe.db.get_value("User", frappe.session.user, "mobile_no")
    if not mobile:
        return None

    lead = frappe.db.get_value(
        "Travel Lead",
        {"mobile": mobile},
        [
            "name", "lead_name", "mobile", "email", "status",
            "assigned_consultant", "tour_type_pref",
            "interested_destination", "travel_month",
            "pax_count", "budget_per_person",
        ],
        as_dict=True,
    )
    if not lead:
        return None

    bookings = []
    customer = frappe.db.get_value("Customer", {"mobile_no": mobile}, "name")

    if customer:
        raw = frappe.get_all(
            "Booking",
            filters={"customer": customer, "docstatus": ["!=", 2]},
            fields=[
                "name", "tour_package", "departure_date", "return_date",
                "total_pax", "adult_pax", "child_pax", "infant_pax",
                "room_category", "base_amount", "addons_total", "gst_amount",
                "tcs_amount", "discount_amount", "grand_total",
                "advance_paid", "balance_due", "balance_due_date",
                "payment_status", "booking_status", "sales_consultant",
                "special_requests", "destination", "creation",
            ],
            order_by="departure_date desc",
        )

        for b in raw:
            bdict = b.copy()

            # Pax details
            bdict["pax_details"] = frappe.get_all(
                "Booking Pax",
                filters={"parent": b["name"]},
                fields=[
                    "pax_name", "pax_type", "age", "gender",
                    "id_type", "id_number", "passport_expiry",
                    "nationality", "dietary_pref", "visa_status",
                ],
            )

            # Itinerary days from linked Tour Package
            if b.get("tour_package"):
                pkg_doc = frappe.db.get_value(
                    "Tour Package", b["tour_package"], "itinerary"
                )
                if pkg_doc:
                    bdict["itinerary_days"] = frappe.get_all(
                        "Itinerary Day",
                        filters={"parent": pkg_doc},
                        fields=[
                            "day_number", "day_title",
                            "morning", "afternoon", "evening", "hotel",
                        ],
                        order_by="day_number asc",
                    )

            bookings.append(bdict)

    return {"lead": lead, "bookings": bookings}


# ──────────────────────────────────────────────────────────────────
# ENQUIRY
# ──────────────────────────────────────────────────────────────────

@frappe.whitelist()
def update_lead_enquiry(destination, tour_type, travel_month, pax_count,
                        budget=0, notes=""):
    """Update the customer's Travel Lead with a new enquiry."""
    if frappe.session.user == "Guest":
        return {"success": False, "error": "Not logged in."}

    mobile = frappe.db.get_value("User", frappe.session.user, "mobile_no")
    if not mobile:
        return {"success": False}

    lead_name = frappe.db.get_value("Travel Lead", {"mobile": mobile}, "name")
    if not lead_name:
        return {"success": False, "error": "Lead not found."}

    lead = frappe.get_doc("Travel Lead", lead_name)

    if lead.status == "Converted":
        # Converted customer — create a fresh follow-up lead
        new_lead = frappe.get_doc({
            "doctype": "Travel Lead",
            "lead_name": lead.lead_name,
            "mobile": lead.mobile,
            "email": lead.email,
            "source": "Website",
            "interested_destination": destination,
            "tour_type_pref": tour_type,
            "travel_month": travel_month,
            "pax_count": pax_count,
            "budget_per_person": budget,
            "status": "New",
        })
        new_lead.flags.ignore_permissions = True
        new_lead.insert()
    else:
        lead.interested_destination = destination
        lead.tour_type_pref         = tour_type
        lead.travel_month           = travel_month
        lead.pax_count              = pax_count
        lead.budget_per_person      = budget
        if notes:
            lead.add_comment("Comment", text=f"Portal enquiry note: {notes}")
        if lead.status in ("New", "Contacted"):
            lead.status = "New"
        lead.flags.ignore_permissions = True
        lead.save()

    frappe.db.commit()
    return {"success": True}


# ──────────────────────────────────────────────────────────────────
# PROFILE UPDATE
# ──────────────────────────────────────────────────────────────────

@frappe.whitelist()
def update_profile(lead_name, email, tour_type_pref, interested_destination=""):
    """Update name, email, tour preference, and destination on the Travel Lead."""
    if frappe.session.user == "Guest":
        return {"success": False}

    mobile = frappe.db.get_value("User", frappe.session.user, "mobile_no")
    if not mobile:
        return {"success": False}

    lead_id = frappe.db.get_value("Travel Lead", {"mobile": mobile}, "name")
    if not lead_id:
        return {"success": False}

    update_fields = {
        "lead_name":             lead_name,
        "email":                 email,
        "tour_type_pref":        tour_type_pref,
    }
    if interested_destination:
        update_fields["interested_destination"] = interested_destination

    frappe.db.set_value("Travel Lead", lead_id, update_fields)

    # Mirror to User record
    frappe.db.set_value("User", frappe.session.user, {
        "first_name": lead_name.split()[0] if lead_name else "",
        "email": email,
    })

    frappe.db.commit()
    return {"success": True}


# ──────────────────────────────────────────────────────────────────
# PAYMENT LINK
# ──────────────────────────────────────────────────────────────────

@frappe.whitelist()
def create_payment_link(booking_name):
    """Generate a Razorpay payment link for the balance due on a booking."""
    if frappe.session.user == "Guest":
        return {"success": False}

    mobile = frappe.db.get_value("User", frappe.session.user, "mobile_no")
    customer = frappe.db.get_value("Customer", {"mobile_no": mobile}, "name")
    if not customer:
        return {"success": False, "error": "Customer not found."}

    booking = frappe.db.get_value(
        "Booking",
        {"name": booking_name, "customer": customer},
        ["name", "balance_due", "grand_total"],
        as_dict=True,
    )
    if not booking or booking.balance_due <= 0:
        return {"success": False, "error": "No balance due on this booking."}

    try:
        from travel_tour.api.payment_gateway import create_payment_link as _make
        url = _make(
            booking_name,
            booking.balance_due,
            f"Balance payment for booking {booking_name}",
        )
        return {"success": True, "url": url}
    except Exception as e:
        frappe.log_error(str(e), "Portal payment link error")
        return {"success": False, "error": "Payment gateway error. Please contact us."}
