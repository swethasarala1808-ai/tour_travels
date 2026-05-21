"""
travel_tour/www/founder_dash.py
Founder Dashboard Backend — uses EXACT field names from Travel Tour doctypes.

Travel Lead fields:  full_name, customer, email_id, mobile_no, pax_count,
                     preferred_month, source, assigned_consultant, status,
                     interest_tags, remarks, converted_booking, suggested_package
Booking fields:      customer, customer_mobile, tour_package, departure_date,
                     total_pax, sales_consultant, base_amount, discount_amount,
                     gst_amount, tcs_amount, grand_total
Booking Pax fields:  pax_name, pax_age, pax_gender, passport_number, passport_expiry
Tour Package fields: package_name, tour_type, destination, duration_nights,
                     duration_days, visa_required, description
Visa Application:    booking, applicant_name, passport_number, passport_expiry,
                     destination_country, visa_type, departure_date, status
"""
import frappe
from frappe.utils import nowdate, add_days, flt, cint


def get_context(context):
    context.no_cache = 1
    context.show_sidebar = False
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect-to=/founder_dash"
        raise frappe.Redirect
    roles = frappe.get_roles(frappe.session.user)
    if not {"System Manager", "Administrator", "Founder"}.intersection(set(roles)):
        frappe.local.flags.redirect_location = "/login"
        raise frappe.Redirect


# ── MAIN LOADER ────────────────────────────────────────────────────

@frappe.whitelist()
def get_founder_data():
    _check_access()
    user = frappe.get_doc("User", frappe.session.user)
    return {
        "founder": {
            "full_name":  user.full_name or frappe.session.user,
            "first_name": (user.full_name or "Founder").split()[0],
        },
        "stats":           _stats(),
        "monthly_revenue": _monthly_revenue(),
        "leads":           _leads(),
        "bookings":        _bookings(),
        "packages":        _packages(),
        "customers":       _customers(),
        "team":            _team(),
    }


# ── STATS ──────────────────────────────────────────────────────────

def _stats():
    today = nowdate()
    d30   = add_days(today, 30)

    # Run each query safely
    def safe_sql(sql, default=0):
        try:
            r = frappe.db.sql(sql)
            return flt(r[0][0]) if r else default
        except Exception:
            return default

    def safe_count(dt, filters):
        try:
            return frappe.db.count(dt, filters)
        except Exception:
            return 0

    total_revenue = safe_sql(
        "SELECT COALESCE(SUM(grand_total),0) FROM `tabBooking` WHERE docstatus!=2"
    )
    balance_due = safe_sql("""
        SELECT COALESCE(SUM(grand_total - COALESCE(
            (SELECT COALESCE(SUM(amount),0) FROM `tabPayment Entry Reference`
             WHERE reference_name=b.name), 0
        )),0)
        FROM `tabBooking` b WHERE docstatus=1
    """)
    # Simpler balance: grand_total sum minus what's been submitted
    active_bk = safe_count("Booking", {"docstatus": ["!=", 2]})
    open_leads = safe_count("Travel Lead", {"status": ["not in", ["Converted", "Lost", "Closed"]]})
    deps_30d   = safe_count("Booking", {
        "departure_date": ["between", [today, d30]],
        "docstatus": ["!=", 2],
    })

    return {
        "total_revenue":     total_revenue,
        "active_bookings":   cint(active_bk),
        "total_balance_due": balance_due,
        "open_leads":        cint(open_leads),
        "departures_30d":    cint(deps_30d),
    }


def _monthly_revenue():
    try:
        rows = frappe.db.sql("""
            SELECT MONTH(departure_date) AS mnum,
                   MONTHNAME(departure_date) AS mname,
                   COALESCE(SUM(grand_total),0) AS rev
            FROM `tabBooking`
            WHERE docstatus!=2 AND YEAR(departure_date)=YEAR(CURDATE())
            GROUP BY mnum, mname ORDER BY mnum
        """, as_dict=True)
    except Exception:
        rows = []
    m_map  = {r["mnum"]: r for r in rows}
    labels = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    return [{"month": labels[i], "rev": flt(m_map.get(i+1, {}).get("rev", 0))} for i in range(12)]


# ── LEADS ──────────────────────────────────────────────────────────

def _leads():
    try:
        rows = frappe.get_all(
            "Travel Lead",
            fields=[
                "name", "full_name", "email_id", "mobile_no",
                "status", "source", "pax_count", "preferred_month",
                "assigned_consultant", "remarks", "suggested_package",
                "converted_booking", "creation", "modified",
            ],
            order_by="creation desc",
            limit=500,
        )
    except Exception:
        rows = []

    result = []
    for l in rows:
        result.append({
            "name":                   l.get("name"),
            "lead_name":              l.get("full_name") or l.get("name"),
            "mobile":                 l.get("mobile_no") or "",
            "email":                  l.get("email_id") or "",
            "status":                 l.get("status") or "New",
            "interested_destination": "",   # not a field — filled from suggested_package below
            "tour_type_pref":         "",
            "travel_month":           l.get("preferred_month") or "",
            "pax_count":              cint(l.get("pax_count") or 0),
            "budget_per_person":      0,
            "assigned_consultant":    l.get("assigned_consultant") or "",
            "notes":                  l.get("remarks") or "",
            "source":                 l.get("source") or "",
            "creation":               str(l.get("creation") or ""),
        })
    return result


@frappe.whitelist()
def create_lead(**kwargs):
    _check_access()
    try:
        doc = frappe.get_doc({
            "doctype":             "Travel Lead",
            "full_name":           kwargs.get("lead_name") or kwargs.get("full_name", ""),
            "email_id":            kwargs.get("email", ""),
            "mobile_no":           kwargs.get("mobile", ""),
            "pax_count":           cint(kwargs.get("pax_count", 0)),
            "preferred_month":     kwargs.get("travel_month", ""),
            "source":              kwargs.get("source", "Manual Entry"),
            "assigned_consultant": kwargs.get("assigned_consultant", ""),
            "status":              kwargs.get("status", "New"),
            "remarks":             kwargs.get("notes", ""),
        })
        doc.flags.ignore_permissions = True
        doc.insert()
        frappe.db.commit()
        return {"success": True, "name": doc.name}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "create_lead")
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def update_lead(**kwargs):
    _check_access()
    lead_id = kwargs.get("lead_id")
    if not lead_id or not frappe.db.exists("Travel Lead", lead_id):
        return {"success": False, "error": "Lead not found."}
    try:
        doc = frappe.get_doc("Travel Lead", lead_id)
        if kwargs.get("lead_name"):    doc.full_name           = kwargs["lead_name"]
        if kwargs.get("mobile"):       doc.mobile_no           = kwargs["mobile"]
        if kwargs.get("email"):        doc.email_id            = kwargs["email"]
        if kwargs.get("pax_count"):    doc.pax_count           = cint(kwargs["pax_count"])
        if kwargs.get("travel_month"): doc.preferred_month     = kwargs["travel_month"]
        if kwargs.get("status"):       doc.status              = kwargs["status"]
        if kwargs.get("assigned_consultant"): doc.assigned_consultant = kwargs["assigned_consultant"]
        if kwargs.get("notes"):        doc.remarks             = kwargs["notes"]
        doc.flags.ignore_permissions = True
        doc.save()
        frappe.db.commit()
        return {"success": True}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "update_lead")
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def delete_record(doctype, record_name):
    _check_access()
    type_map = {
        "lead":    "Travel Lead",
        "package": "Tour Package",
        "booking": "Booking",
    }
    dt = type_map.get(str(doctype).lower(), doctype)
    if not frappe.db.exists(dt, record_name):
        return {"success": False, "error": "Not found."}
    try:
        frappe.delete_doc(dt, record_name, force=True, ignore_permissions=True)
        frappe.db.commit()
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ── BOOKINGS ───────────────────────────────────────────────────────

def _bookings():
    try:
        rows = frappe.get_all(
            "Booking",
            filters={"docstatus": ["!=", 2]},
            fields=[
                "name", "customer", "customer_mobile", "tour_package",
                "departure_date", "total_pax", "sales_consultant",
                "base_amount", "discount_amount", "gst_amount",
                "tcs_amount", "grand_total", "docstatus", "creation",
            ],
            order_by="creation desc",
            limit=500,
        )
    except Exception:
        rows = []

    # Get Booking Pax child records
    result = []
    for b in rows:
        grand   = flt(b.get("grand_total") or 0)
        # Get advance paid from Payment Entry
        advance = _get_advance_paid(b["name"])
        balance = max(0, grand - advance)

        # Map booking_status from docstatus
        ds = cint(b.get("docstatus", 0))
        if ds == 0:
            bk_status = "Draft"
        elif ds == 1:
            bk_status = "Confirmed"
        else:
            bk_status = "Cancelled"

        pax = []
        try:
            pax = frappe.get_all(
                "Booking Pax",
                filters={"parent": b["name"]},
                fields=["pax_name", "pax_age", "pax_gender",
                        "passport_number", "passport_expiry"],
            )
            # normalize for frontend
            for p in pax:
                p["id_number"]       = p.get("passport_number") or ""
                p["pax_type"]        = "Adult"
                p["visa_status"]     = "Not Applied"
        except Exception:
            pax = []

        result.append({
            "name":             b["name"],
            "customer":         b.get("customer") or "",
            "tour_package":     b.get("tour_package") or "",
            "departure_date":   str(b.get("departure_date") or ""),
            "return_date":      "",
            "total_pax":        cint(b.get("total_pax") or 0),
            "adult_pax":        cint(b.get("total_pax") or 0),
            "child_pax":        0,
            "room_category":    "",
            "base_amount":      flt(b.get("base_amount") or 0),
            "addons_total":     0,
            "gst_amount":       flt(b.get("gst_amount") or 0),
            "tcs_amount":       flt(b.get("tcs_amount") or 0),
            "discount_amount":  flt(b.get("discount_amount") or 0),
            "grand_total":      grand,
            "advance_paid":     advance,
            "balance_due":      balance,
            "balance_due_date": "",
            "payment_status":   "Paid" if balance <= 0 else "Partial",
            "booking_status":   bk_status,
            "sales_consultant": b.get("sales_consultant") or "",
            "special_requests": "",
            "destination":      _get_package_destination(b.get("tour_package")),
            "creation":         str(b.get("creation") or ""),
            "pax_details":      pax,
        })
    return result


def _get_advance_paid(booking_name):
    """Sum all submitted Payment Entry amounts linked to this booking."""
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


def _get_package_destination(pkg_name):
    if not pkg_name:
        return ""
    try:
        return frappe.db.get_value("Tour Package", pkg_name, "destination") or ""
    except Exception:
        return ""


@frappe.whitelist()
def create_booking(**kwargs):
    _check_access()
    try:
        grand   = flt(kwargs.get("grand_total", 0))
        advance = flt(kwargs.get("advance_paid", 0))
        doc = frappe.get_doc({
            "doctype":          "Booking",
            "customer":         kwargs.get("customer", ""),
            "customer_mobile":  kwargs.get("customer_mobile", ""),
            "tour_package":     kwargs.get("tour_package", ""),
            "departure_date":   kwargs.get("departure_date"),
            "total_pax":        cint(kwargs.get("total_pax") or kwargs.get("adult_pax") or 0),
            "sales_consultant": kwargs.get("sales_consultant", ""),
            "base_amount":      grand,
            "grand_total":      grand,
        })
        doc.flags.ignore_permissions = True
        doc.insert()
        frappe.db.commit()
        return {"success": True, "name": doc.name}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "create_booking")
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def update_booking(**kwargs):
    _check_access()
    bid = kwargs.get("booking_id")
    if not frappe.db.exists("Booking", bid):
        return {"success": False, "error": "Booking not found."}
    try:
        doc = frappe.get_doc("Booking", bid)
        if kwargs.get("tour_package"):    doc.tour_package     = kwargs["tour_package"]
        if kwargs.get("departure_date"):  doc.departure_date   = kwargs["departure_date"]
        if kwargs.get("sales_consultant"):doc.sales_consultant = kwargs["sales_consultant"]
        if kwargs.get("grand_total"):
            doc.grand_total  = flt(kwargs["grand_total"])
            doc.base_amount  = flt(kwargs["grand_total"])
        if kwargs.get("total_pax") or kwargs.get("adult_pax"):
            doc.total_pax = cint(kwargs.get("total_pax") or kwargs.get("adult_pax") or 0)
        doc.flags.ignore_permissions = True
        doc.save()
        frappe.db.commit()
        return {"success": True}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "update_booking")
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def update_booking_status(booking_name, status):
    _check_access()
    if not frappe.db.exists("Booking", booking_name):
        return {"success": False, "error": "Not found."}
    try:
        doc = frappe.get_doc("Booking", booking_name)
        # Frappe uses docstatus: 0=Draft, 1=Submitted, 2=Cancelled
        status_map = {"Draft": 0, "Confirmed": 1, "Cancelled": 2, "Completed": 1}
        ds = status_map.get(status, 0)
        if ds == 2 and doc.docstatus == 1:
            doc.cancel()
        elif ds == 1 and doc.docstatus == 0:
            doc.submit()
        else:
            doc.flags.ignore_permissions = True
            doc.save()
        frappe.db.commit()
        return {"success": True}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "update_booking_status")
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def record_payment(**kwargs):
    _check_access()
    booking_name = kwargs.get("booking_name")
    amount       = flt(kwargs.get("amount", 0))
    if not booking_name or amount <= 0:
        return {"success": False, "error": "Invalid booking or amount."}
    if not frappe.db.exists("Booking", booking_name):
        return {"success": False, "error": "Booking not found."}
    try:
        bk = frappe.get_doc("Booking", booking_name)
        bk.add_comment("Comment", text=(
            f"Payment of ₹{amount:,.0f} recorded via "
            f"{kwargs.get('mode','—')} on {kwargs.get('payment_date', nowdate())}. "
            f"Ref: {kwargs.get('reference','—')}. {kwargs.get('notes','')}"
        ))
        frappe.db.commit()
        return {"success": True}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "record_payment")
        return {"success": False, "error": str(e)}


# ── PACKAGES ───────────────────────────────────────────────────────

def _packages():
    try:
        rows = frappe.get_all(
            "Tour Package",
            fields=[
                "name", "package_name", "destination", "tour_type",
                "duration_nights", "duration_days", "visa_required",
                "description", "creation",
            ],
            order_by="creation desc",
        )
    except Exception:
        rows = []

    result = []
    for p in rows:
        # Get price from Package Pricing child table
        price = _get_package_price(p["name"])
        # Get booking count
        try:
            bcount = frappe.db.count("Booking", {"tour_package": p["name"], "docstatus": ["!=", 2]})
        except Exception:
            bcount = 0

        result.append({
            "name":             p["name"],
            "package_name":     p.get("package_name") or p["name"],
            "destination":      p.get("destination") or "",
            "tour_type":        p.get("tour_type") or "",
            "duration":         cint(p.get("duration_days") or 0),
            "nights":           cint(p.get("duration_nights") or 0),
            "price_per_person": price,
            "status":           "Active",
            "description":      p.get("description") or "",
            "bookings_count":   bcount,
        })
    return result


def _get_package_price(pkg_name):
    """Get lowest price from Package Pricing child table."""
    try:
        r = frappe.db.sql("""
            SELECT MIN(price_per_person)
            FROM `tabPackage Pricing`
            WHERE parent=%s
        """, pkg_name)
        return flt(r[0][0]) if r and r[0][0] else 0
    except Exception:
        return 0


@frappe.whitelist()
def save_package(**kwargs):
    _check_access()
    pkg_id = kwargs.get("pkg_id")
    try:
        if pkg_id and frappe.db.exists("Tour Package", pkg_id):
            doc = frappe.get_doc("Tour Package", pkg_id)
        else:
            doc = frappe.new_doc("Tour Package")

        if kwargs.get("package_name"): doc.package_name    = kwargs["package_name"]
        if kwargs.get("destination"):  doc.destination      = kwargs["destination"]
        if kwargs.get("tour_type"):    doc.tour_type        = kwargs["tour_type"]
        if kwargs.get("duration"):     doc.duration_days    = cint(kwargs["duration"])
        if kwargs.get("nights"):       doc.duration_nights  = cint(kwargs["nights"])
        if kwargs.get("description"):  doc.description      = kwargs["description"]

        doc.flags.ignore_permissions = True
        doc.insert() if doc.is_new() else doc.save()
        frappe.db.commit()
        return {"success": True, "name": doc.name}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "save_package")
        return {"success": False, "error": str(e)}


# ── CUSTOMERS ──────────────────────────────────────────────────────

def _customers():
    """Build customer list from Travel Lead (customer field) + Bookings."""
    try:
        # Get distinct customers from Booking
        rows = frappe.db.sql("""
            SELECT
                customer,
                customer_mobile,
                COUNT(*) as total_bookings,
                COALESCE(SUM(grand_total), 0) as total_spent,
                MAX(departure_date) as last_departure
            FROM `tabBooking`
            WHERE docstatus != 2 AND customer IS NOT NULL AND customer != ''
            GROUP BY customer, customer_mobile
            ORDER BY total_bookings DESC
            LIMIT 300
        """, as_dict=True)
    except Exception:
        rows = []

    result = []
    for r in rows:
        # Find last destination
        try:
            last_dest = frappe.db.get_value(
                "Booking",
                {"customer": r["customer"], "docstatus": ["!=", 2]},
                "tour_package",
                order_by="departure_date desc",
            )
        except Exception:
            last_dest = ""

        result.append({
            "name":           r["customer"],
            "customer_name":  r["customer"],
            "mobile":         r.get("customer_mobile") or "",
            "email":          "",
            "total_bookings": cint(r["total_bookings"]),
            "total_spent":    flt(r["total_spent"]),
            "last_trip":      last_dest or "—",
        })

    # Also include Travel Leads that have no bookings yet
    try:
        leads = frappe.get_all(
            "Travel Lead",
            filters={"status": ["not in", ["Lost", "Closed"]]},
            fields=["name", "full_name", "mobile_no", "email_id", "status"],
            limit=200,
        )
        existing = {r["customer"] for r in rows}
        for l in leads:
            if l.get("full_name") and l["full_name"] not in existing:
                result.append({
                    "name":           l["name"],
                    "customer_name":  l.get("full_name") or l["name"],
                    "mobile":         l.get("mobile_no") or "",
                    "email":          l.get("email_id") or "",
                    "total_bookings": 0,
                    "total_spent":    0,
                    "last_trip":      "—",
                })
    except Exception:
        pass

    return result


# ── TEAM ───────────────────────────────────────────────────────────

def _team():
    try:
        members = frappe.get_all(
            "Employee",
            filters={"status": "Active"},
            fields=["name", "employee_name", "designation",
                    "cell_number", "company_email", "status"],
            order_by="employee_name",
        )
    except Exception:
        members = []

    result = []
    for m in members:
        name = m.get("employee_name") or m["name"]
        try:
            leads_handled = frappe.db.count("Travel Lead", {"assigned_consultant": name})
        except Exception:
            leads_handled = 0
        try:
            bk_confirmed = frappe.db.count("Booking", {
                "sales_consultant": name, "docstatus": 1
            })
        except Exception:
            bk_confirmed = 0

        result.append({
            "name":               m["name"],
            "employee_name":      name,
            "role":               m.get("designation") or "Staff",
            "mobile":             m.get("cell_number") or "",
            "email":              m.get("company_email") or "",
            "status":             m.get("status") or "Active",
            "leads_handled":      leads_handled,
            "bookings_confirmed": bk_confirmed,
        })
    return result


@frappe.whitelist()
def save_team_member(**kwargs):
    _check_access()
    try:
        doc = frappe.new_doc("Employee")
        doc.employee_name   = kwargs.get("employee_name", "")
        doc.designation     = kwargs.get("role", "Sales Consultant")
        doc.cell_number     = kwargs.get("mobile", "")
        doc.company_email   = kwargs.get("email", "")
        doc.status          = "Active"
        doc.date_of_joining = nowdate()
        doc.flags.ignore_permissions = True
        doc.insert()
        frappe.db.commit()
        return {"success": True, "name": doc.name}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "save_team_member")
        return {"success": False, "error": str(e)}


# ── VISA ───────────────────────────────────────────────────────────

@frappe.whitelist()
def update_visa_status(booking_name, pax_name, visa_status):
    _check_access()
    try:
        # Update in Visa Application
        va = frappe.db.get_value(
            "Visa Application",
            {"booking": booking_name, "applicant_name": pax_name},
            "name"
        )
        if va:
            frappe.db.set_value("Visa Application", va, "status", visa_status)
            frappe.db.commit()
            return {"success": True}
        # Fallback: update Booking Pax comment
        bk = frappe.get_doc("Booking", booking_name)
        bk.add_comment("Comment", text=f"Visa status for {pax_name}: {visa_status}")
        frappe.db.commit()
        return {"success": True}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "update_visa_status")
        return {"success": False, "error": str(e)}


# ── DEPARTURES (from Bookings) ─────────────────────────────────────

def _departures():
    try:
        rows = frappe.get_all(
            "Booking",
            filters={
                "docstatus": 1,
                "departure_date": [">=", add_days(nowdate(), -1)],
            },
            fields=["name", "customer", "tour_package", "departure_date",
                    "total_pax", "sales_consultant"],
            order_by="departure_date asc",
            limit=100,
        )
        for r in rows:
            r["destination"]     = _get_package_destination(r.get("tour_package"))
            r["booking_status"]  = "Confirmed"
        return rows
    except Exception:
        return []


# ── ACCESS GUARD ───────────────────────────────────────────────────

def _check_access():
    if frappe.session.user == "Guest":
        frappe.throw("Not logged in.", frappe.AuthenticationError)
    roles = frappe.get_roles(frappe.session.user)
    if not {"Founder", "System Manager", "Administrator"}.intersection(set(roles)):
        frappe.throw("Access denied.", frappe.PermissionError)
