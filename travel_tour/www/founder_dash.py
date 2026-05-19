"""
travel_tour/www/founder_dash.py
Founder Dashboard — Full CRUD APIs
All methods require the logged-in user to be the business owner (Founder role).
"""

import frappe
from frappe.utils import nowdate, getdate, add_days, flt, cint


# ──────────────────────────────────────────────────────────────────
# PAGE GUARD
# ──────────────────────────────────────────────────────────────────

def get_context(context):
    context.no_cache = 1
    context.show_sidebar = False

    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login"
        raise frappe.Redirect

    # Allow Founder, System Manager, or Administrator
    user_roles = frappe.get_roles(frappe.session.user)
    allowed = {"Founder", "System Manager", "Administrator"}
    if not allowed.intersection(set(user_roles)):
        frappe.local.flags.redirect_location = "/login"
        raise frappe.Redirect


# ──────────────────────────────────────────────────────────────────
# MAIN DATA LOADER
# ──────────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_founder_data():
    """Return full dashboard data for the founder."""
    _assert_founder()

    user = frappe.get_doc("User", frappe.session.user)

    return {
        "founder": {
            "full_name": user.full_name or frappe.session.user,
            "first_name": user.first_name or user.full_name or "Founder",
            "email": user.email,
        },
        "stats":           _get_stats(),
        "monthly_revenue": _get_monthly_revenue(),
        "leads":           _get_leads(),
        "bookings":        _get_bookings(),
        "packages":        _get_packages(),
        "customers":       _get_customers(),
        "team":            _get_team(),
        "departures":      _get_departures(),
    }


# ──────────────────────────────────────────────────────────────────
# STATS
# ──────────────────────────────────────────────────────────────────

def _get_stats():
    today = nowdate()
    thirty_days = add_days(today, 30)

    total_revenue = frappe.db.sql("""
        SELECT COALESCE(SUM(advance_paid), 0)
        FROM `tabBooking`
        WHERE docstatus != 2
    """)[0][0] or 0

    active_bookings = frappe.db.count("Booking", {
        "booking_status": ["in", ["Confirmed", "Draft"]],
        "docstatus": ["!=", 2],
    })

    total_balance_due = frappe.db.sql("""
        SELECT COALESCE(SUM(balance_due), 0)
        FROM `tabBooking`
        WHERE docstatus != 2 AND balance_due > 0
    """)[0][0] or 0

    open_leads = frappe.db.count("Travel Lead", {
        "status": ["not in", ["Converted", "Lost"]],
    })

    departures_30d = frappe.db.count("Booking", {
        "booking_status": "Confirmed",
        "departure_date": ["between", [today, thirty_days]],
        "docstatus": ["!=", 2],
    })

    return {
        "total_revenue":     flt(total_revenue),
        "active_bookings":   cint(active_bookings),
        "total_balance_due": flt(total_balance_due),
        "open_leads":        cint(open_leads),
        "departures_30d":    cint(departures_30d),
    }


# ──────────────────────────────────────────────────────────────────
# MONTHLY REVENUE
# ──────────────────────────────────────────────────────────────────

def _get_monthly_revenue():
    rows = frappe.db.sql("""
        SELECT
            MONTH(departure_date)  AS mnum,
            MONTHNAME(departure_date) AS month,
            COALESCE(SUM(advance_paid), 0) AS rev
        FROM `tabBooking`
        WHERE
            docstatus != 2
            AND YEAR(departure_date) = YEAR(CURDATE())
        GROUP BY mnum, month
        ORDER BY mnum
    """, as_dict=True)

    month_map = {r["mnum"]: r for r in rows}
    months = ["Jan","Feb","Mar","Apr","May","Jun",
              "Jul","Aug","Sep","Oct","Nov","Dec"]
    return [
        {"month": months[i], "rev": flt(month_map.get(i+1, {}).get("rev", 0))}
        for i in range(12)
    ]


# ──────────────────────────────────────────────────────────────────
# LEADS
# ──────────────────────────────────────────────────────────────────

def _get_leads():
    return frappe.get_all(
        "Travel Lead",
        fields=[
            "name", "lead_name", "mobile", "email", "status",
            "interested_destination", "tour_type_pref", "travel_month",
            "pax_count", "budget_per_person", "assigned_consultant",
            "notes", "creation", "modified",
        ],
        order_by="creation desc",
        limit=200,
    )


@frappe.whitelist()
def create_lead(**kwargs):
    _assert_founder()
    doc = frappe.get_doc({
        "doctype": "Travel Lead",
        "lead_name":              kwargs.get("lead_name"),
        "mobile":                 kwargs.get("mobile"),
        "email":                  kwargs.get("email", ""),
        "interested_destination": kwargs.get("interested_destination", ""),
        "tour_type_pref":         kwargs.get("tour_type_pref", ""),
        "travel_month":           kwargs.get("travel_month", ""),
        "pax_count":              cint(kwargs.get("pax_count", 0)),
        "budget_per_person":      flt(kwargs.get("budget_per_person", 0)),
        "status":                 kwargs.get("status", "New"),
        "assigned_consultant":    kwargs.get("assigned_consultant", ""),
        "notes":                  kwargs.get("notes", ""),
        "source":                 kwargs.get("source", "Manual"),
    })
    doc.flags.ignore_permissions = True
    doc.insert()
    frappe.db.commit()
    return {"success": True, "name": doc.name}


@frappe.whitelist()
def update_lead(**kwargs):
    _assert_founder()
    lead_id = kwargs.get("lead_id")
    if not lead_id or not frappe.db.exists("Travel Lead", lead_id):
        return {"success": False, "error": "Lead not found."}

    doc = frappe.get_doc("Travel Lead", lead_id)
    doc.lead_name              = kwargs.get("lead_name", doc.lead_name)
    doc.mobile                 = kwargs.get("mobile", doc.mobile)
    doc.email                  = kwargs.get("email", doc.email)
    doc.interested_destination = kwargs.get("interested_destination", doc.interested_destination)
    doc.tour_type_pref         = kwargs.get("tour_type_pref", doc.tour_type_pref)
    doc.travel_month           = kwargs.get("travel_month", doc.travel_month)
    doc.pax_count              = cint(kwargs.get("pax_count", doc.pax_count))
    doc.budget_per_person      = flt(kwargs.get("budget_per_person", doc.budget_per_person))
    doc.status                 = kwargs.get("status", doc.status)
    doc.assigned_consultant    = kwargs.get("assigned_consultant", doc.assigned_consultant)
    if kwargs.get("notes"):
        doc.notes = kwargs["notes"]

    doc.flags.ignore_permissions = True
    doc.save()
    frappe.db.commit()
    return {"success": True}


@frappe.whitelist()
def delete_record(doctype, record_name):
    _assert_founder()
    _doctype_map = {
        "lead":    "Travel Lead",
        "package": "Tour Package",
        "team":    "Employee",
        "booking": "Booking",
    }
    dt = _doctype_map.get(doctype, doctype)
    if not frappe.db.exists(dt, record_name):
        return {"success": False, "error": "Record not found."}
    try:
        frappe.delete_doc(dt, record_name, force=True, ignore_permissions=True)
        frappe.db.commit()
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ──────────────────────────────────────────────────────────────────
# BOOKINGS
# ──────────────────────────────────────────────────────────────────

def _get_bookings():
    bookings = frappe.get_all(
        "Booking",
        filters={"docstatus": ["!=", 2]},
        fields=[
            "name", "customer", "tour_package", "departure_date", "return_date",
            "total_pax", "adult_pax", "child_pax", "infant_pax",
            "room_category", "base_amount", "addons_total", "gst_amount",
            "tcs_amount", "discount_amount", "grand_total",
            "advance_paid", "balance_due", "balance_due_date",
            "payment_status", "booking_status", "sales_consultant",
            "special_requests", "destination", "creation", "modified",
        ],
        order_by="creation desc",
        limit=500,
    )

    for b in bookings:
        b["pax_details"] = frappe.get_all(
            "Booking Pax",
            filters={"parent": b["name"]},
            fields=[
                "pax_name", "pax_type", "age", "gender",
                "id_type", "id_number", "passport_expiry",
                "nationality", "dietary_pref", "visa_status",
            ],
        )

    return bookings


@frappe.whitelist()
def create_booking(**kwargs):
    _assert_founder()
    adults   = cint(kwargs.get("adult_pax", 0))
    children = cint(kwargs.get("child_pax", 0))

    # Auto-create or find customer
    customer_name = _get_or_create_customer(kwargs.get("customer", ""))

    doc = frappe.get_doc({
        "doctype":           "Booking",
        "customer":          customer_name,
        "tour_package":      kwargs.get("tour_package", ""),
        "departure_date":    kwargs.get("departure_date"),
        "return_date":       kwargs.get("return_date"),
        "adult_pax":         adults,
        "child_pax":         children,
        "total_pax":         adults + children,
        "room_category":     kwargs.get("room_category", "Standard"),
        "grand_total":       flt(kwargs.get("grand_total", 0)),
        "advance_paid":      flt(kwargs.get("advance_paid", 0)),
        "balance_due":       flt(kwargs.get("grand_total", 0)) - flt(kwargs.get("advance_paid", 0)),
        "balance_due_date":  kwargs.get("balance_due_date", ""),
        "sales_consultant":  kwargs.get("sales_consultant", ""),
        "booking_status":    kwargs.get("booking_status", "Draft"),
        "payment_status":    "Partial" if flt(kwargs.get("advance_paid", 0)) > 0 else "Pending",
        "special_requests":  kwargs.get("special_requests", ""),
        "destination":       kwargs.get("destination", ""),
    })
    doc.flags.ignore_permissions = True
    doc.insert()
    frappe.db.commit()
    return {"success": True, "name": doc.name}


@frappe.whitelist()
def update_booking(**kwargs):
    _assert_founder()
    booking_id = kwargs.get("booking_id")
    if not frappe.db.exists("Booking", booking_id):
        return {"success": False, "error": "Booking not found."}

    doc = frappe.get_doc("Booking", booking_id)
    adults   = cint(kwargs.get("adult_pax", doc.adult_pax))
    children = cint(kwargs.get("child_pax", doc.child_pax))
    grand    = flt(kwargs.get("grand_total", doc.grand_total))
    advance  = flt(kwargs.get("advance_paid", doc.advance_paid))

    doc.tour_package     = kwargs.get("tour_package", doc.tour_package)
    doc.departure_date   = kwargs.get("departure_date", doc.departure_date)
    doc.return_date      = kwargs.get("return_date", doc.return_date)
    doc.adult_pax        = adults
    doc.child_pax        = children
    doc.total_pax        = adults + children
    doc.room_category    = kwargs.get("room_category", doc.room_category)
    doc.grand_total      = grand
    doc.advance_paid     = advance
    doc.balance_due      = grand - advance
    doc.balance_due_date = kwargs.get("balance_due_date", doc.balance_due_date)
    doc.sales_consultant = kwargs.get("sales_consultant", doc.sales_consultant)
    doc.booking_status   = kwargs.get("booking_status", doc.booking_status)
    doc.special_requests = kwargs.get("special_requests", doc.special_requests)

    if doc.balance_due <= 0:
        doc.payment_status = "Paid"
    elif advance > 0:
        doc.payment_status = "Partial"
    else:
        doc.payment_status = "Pending"

    doc.flags.ignore_permissions = True
    doc.save()
    frappe.db.commit()
    return {"success": True}


@frappe.whitelist()
def update_booking_status(booking_name, status):
    _assert_founder()
    if not frappe.db.exists("Booking", booking_name):
        return {"success": False, "error": "Booking not found."}
    frappe.db.set_value("Booking", booking_name, "booking_status", status)
    frappe.db.commit()
    return {"success": True}


@frappe.whitelist()
def record_payment(**kwargs):
    _assert_founder()
    booking_name = kwargs.get("booking_name")
    amount       = flt(kwargs.get("amount", 0))

    if not booking_name or amount <= 0:
        return {"success": False, "error": "Invalid booking or amount."}

    if not frappe.db.exists("Booking", booking_name):
        return {"success": False, "error": "Booking not found."}

    doc = frappe.get_doc("Booking", booking_name)
    doc.advance_paid = flt(doc.advance_paid) + amount
    doc.balance_due  = flt(doc.grand_total) - doc.advance_paid
    if doc.balance_due <= 0:
        doc.balance_due    = 0
        doc.payment_status = "Paid"
    else:
        doc.payment_status = "Partial"

    doc.flags.ignore_permissions = True
    doc.save()

    # Log payment in a child table or comment
    doc.add_comment("Comment", text=(
        f"Payment recorded: ₹{amount:,.0f} via {kwargs.get('mode','—')} "
        f"on {kwargs.get('payment_date', nowdate())}. "
        f"Ref: {kwargs.get('reference','—')}. "
        f"Notes: {kwargs.get('notes','')}"
    ))

    frappe.db.commit()
    return {"success": True, "new_balance": doc.balance_due}


# ──────────────────────────────────────────────────────────────────
# PACKAGES
# ──────────────────────────────────────────────────────────────────

def _get_packages():
    pkgs = frappe.get_all(
        "Tour Package",
        fields=[
            "name", "package_name", "destination", "duration", "nights",
            "tour_type", "price_per_person", "status",
            "inclusions", "exclusions", "description",
        ],
        order_by="creation desc",
    )
    for p in pkgs:
        p["bookings_count"] = frappe.db.count("Booking", {
            "tour_package": p["name"],
            "docstatus": ["!=", 2],
        })
    return pkgs


@frappe.whitelist()
def save_package(**kwargs):
    _assert_founder()
    pkg_id = kwargs.get("pkg_id")

    if pkg_id and frappe.db.exists("Tour Package", pkg_id):
        doc = frappe.get_doc("Tour Package", pkg_id)
    else:
        doc = frappe.new_doc("Tour Package")

    doc.package_name     = kwargs.get("package_name", doc.get("package_name", ""))
    doc.destination      = kwargs.get("destination", doc.get("destination", ""))
    doc.duration         = cint(kwargs.get("duration", doc.get("duration", 1)))
    doc.nights           = cint(kwargs.get("nights", doc.get("nights", 0)))
    doc.tour_type        = kwargs.get("tour_type", doc.get("tour_type", "Group"))
    doc.price_per_person = flt(kwargs.get("price_per_person", doc.get("price_per_person", 0)))
    doc.status           = kwargs.get("status", doc.get("status", "Active"))
    doc.inclusions       = kwargs.get("inclusions", doc.get("inclusions", ""))
    doc.exclusions       = kwargs.get("exclusions", doc.get("exclusions", ""))
    doc.description      = kwargs.get("description", doc.get("description", ""))

    doc.flags.ignore_permissions = True
    if doc.is_new():
        doc.insert()
    else:
        doc.save()
    frappe.db.commit()
    return {"success": True, "name": doc.name}


# ──────────────────────────────────────────────────────────────────
# CUSTOMERS
# ──────────────────────────────────────────────────────────────────

def _get_customers():
    customers = frappe.get_all(
        "Customer",
        fields=["name", "customer_name", "mobile_no as mobile", "email_id as email"],
        order_by="creation desc",
        limit=300,
    )
    for c in customers:
        bks = frappe.get_all(
            "Booking",
            filters={"customer": c["name"], "docstatus": ["!=", 2]},
            fields=["name", "grand_total", "destination", "departure_date"],
        )
        c["total_bookings"] = len(bks)
        c["total_spent"]    = sum(flt(b.get("grand_total", 0)) for b in bks)
        if bks:
            latest = max(bks, key=lambda x: x.get("departure_date") or "")
            c["last_trip"] = latest.get("destination") or latest["name"]
        else:
            c["last_trip"] = "—"
    return customers


# ──────────────────────────────────────────────────────────────────
# TEAM
# ──────────────────────────────────────────────────────────────────

def _get_team():
    members = frappe.get_all(
        "Employee",
        filters={"status": ["!=", "Left"]},
        fields=[
            "name", "employee_name", "designation as role",
            "cell_number as mobile", "company_email as email",
            "status",
        ],
        order_by="employee_name",
    )
    for m in members:
        m["leads_handled"]      = frappe.db.count("Travel Lead", {"assigned_consultant": m["employee_name"]})
        m["bookings_confirmed"] = frappe.db.count("Booking", {
            "sales_consultant": m["employee_name"],
            "booking_status": "Confirmed",
            "docstatus": ["!=", 2],
        })
    return members


@frappe.whitelist()
def save_team_member(**kwargs):
    _assert_founder()
    try:
        doc = frappe.new_doc("Employee")
        doc.employee_name  = kwargs.get("employee_name")
        doc.designation    = kwargs.get("role", "Sales Consultant")
        doc.cell_number    = kwargs.get("mobile", "")
        doc.company_email  = kwargs.get("email", "")
        doc.status         = "Active"
        doc.date_of_joining = nowdate()
        doc.flags.ignore_permissions = True
        doc.insert()
        frappe.db.commit()
        return {"success": True, "name": doc.name}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ──────────────────────────────────────────────────────────────────
# DEPARTURES
# ──────────────────────────────────────────────────────────────────

def _get_departures():
    return frappe.get_all(
        "Booking",
        filters={
            "booking_status": "Confirmed",
            "docstatus": ["!=", 2],
            "departure_date": [">=", add_days(nowdate(), -7)],
        },
        fields=[
            "name", "customer", "tour_package", "departure_date", "return_date",
            "total_pax", "destination", "sales_consultant", "booking_status",
        ],
        order_by="departure_date asc",
        limit=100,
    )


# ──────────────────────────────────────────────────────────────────
# VISA
# ──────────────────────────────────────────────────────────────────

@frappe.whitelist()
def update_visa_status(booking_name, pax_name, visa_status):
    _assert_founder()
    pax = frappe.db.get_value(
        "Booking Pax",
        {"parent": booking_name, "pax_name": pax_name},
        "name",
    )
    if not pax:
        return {"success": False, "error": "Pax record not found."}
    frappe.db.set_value("Booking Pax", pax, "visa_status", visa_status)
    frappe.db.commit()
    return {"success": True}


# ──────────────────────────────────────────────────────────────────
# SETTINGS
# ──────────────────────────────────────────────────────────────────

@frappe.whitelist()
def save_settings(**kwargs):
    _assert_founder()
    try:
        settings = frappe.get_single("Travel Tour Settings")
        for k, v in kwargs.items():
            if hasattr(settings, k):
                setattr(settings, k, v)
        settings.flags.ignore_permissions = True
        settings.save()
        frappe.db.commit()
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ──────────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────────

def _assert_founder():
    """Raise PermissionError if not a Founder / System Manager."""
    if frappe.session.user == "Guest":
        frappe.throw("Not logged in.", frappe.PermissionError)
    roles = frappe.get_roles(frappe.session.user)
    if not {"Founder", "System Manager", "Administrator"}.intersection(set(roles)):
        frappe.throw("Insufficient privileges.", frappe.PermissionError)


def _get_or_create_customer(name_or_mobile: str) -> str:
    """Return existing Customer name or create one."""
    if not name_or_mobile:
        return name_or_mobile

    # Try exact match first
    existing = frappe.db.get_value("Customer", {"customer_name": name_or_mobile}, "name")
    if existing:
        return existing

    # Mobile match
    existing = frappe.db.get_value("Customer", {"mobile_no": name_or_mobile}, "name")
    if existing:
        return existing

    # Create new
    cust = frappe.get_doc({
        "doctype":       "Customer",
        "customer_name": name_or_mobile,
        "customer_type": "Individual",
        "customer_group": frappe.db.get_value("Customer Group", {"is_group": 0}, "name") or "Individual",
        "territory":     frappe.db.get_value("Territory", {"is_group": 0}, "name") or "India",
    })
    cust.flags.ignore_permissions = True
    cust.insert()
    frappe.db.commit()
    return cust.name
