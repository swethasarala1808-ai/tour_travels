"""
travel_tour/www/founder_dash.py
Founder Dashboard — reads real Travel Tour doctypes
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


@frappe.whitelist()
def get_founder_data():
    """Main data loader — returns everything the dashboard needs."""
    _assert_founder()

    user = frappe.get_doc("User", frappe.session.user)
    return {
        "founder": {
            "full_name": user.full_name or frappe.session.user,
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


# ── stats ─────────────────────────────────────────────────────────

def _stats():
    today = nowdate()
    d30 = add_days(today, 30)

    total_revenue = flt(frappe.db.sql(
        "SELECT COALESCE(SUM(advance_paid),0) FROM `tabBooking` WHERE docstatus!=2"
    )[0][0])

    active_bk = frappe.db.count("Booking", {
        "booking_status": ["in", ["Confirmed", "Draft"]],
        "docstatus": ["!=", 2],
    })

    balance_due = flt(frappe.db.sql(
        "SELECT COALESCE(SUM(balance_due),0) FROM `tabBooking` WHERE docstatus!=2 AND balance_due>0"
    )[0][0])

    open_leads = frappe.db.count("Travel Lead", {
        "status": ["not in", ["Converted", "Lost"]],
    })

    deps_30d = frappe.db.count("Booking", {
        "booking_status": "Confirmed",
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
    rows = frappe.db.sql("""
        SELECT MONTH(departure_date) AS mnum,
               MONTHNAME(departure_date) AS mname,
               COALESCE(SUM(advance_paid),0) AS rev
        FROM `tabBooking`
        WHERE docstatus!=2 AND YEAR(departure_date)=YEAR(CURDATE())
        GROUP BY mnum, mname ORDER BY mnum
    """, as_dict=True)
    m_map = {r["mnum"]: r for r in rows}
    labels = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    return [{"month": labels[i], "rev": flt(m_map.get(i+1, {}).get("rev", 0))} for i in range(12)]


# ── leads ─────────────────────────────────────────────────────────

def _leads():
    # Try real Travel Lead fields — fall back gracefully
    fields = [
        "name", "status", "creation", "modified",
        "lead_name", "mobile_no", "email_id",
        "interested_destination", "tour_type_pref",
        "travel_month", "pax_count", "budget_per_person",
        "assigned_consultant", "notes", "source",
    ]
    # Only keep fields that exist
    meta = frappe.get_meta("Travel Lead")
    real_fields = {f.fieldname for f in meta.fields}
    real_fields.update({"name", "status", "creation", "modified"})
    safe = [f for f in fields if f in real_fields]

    leads = frappe.get_all("Travel Lead", fields=safe, order_by="creation desc", limit=300)

    # Normalize field names the frontend expects
    for l in leads:
        l.setdefault("lead_name", l.get("full_name") or l.get("customer_name") or l.get("name"))
        l.setdefault("mobile", l.get("mobile_no") or l.get("phone") or "")
        l.setdefault("email", l.get("email_id") or "")
        l.setdefault("interested_destination", l.get("destination") or "")
        l.setdefault("tour_type_pref", l.get("tour_type") or "")
        l.setdefault("travel_month", "")
        l.setdefault("pax_count", 0)
        l.setdefault("budget_per_person", 0)
        l.setdefault("assigned_consultant", "")
        l.setdefault("status", "New")
    return leads


@frappe.whitelist()
def create_lead(**kwargs):
    _assert_founder()
    meta = frappe.get_meta("Travel Lead")
    real_fields = {f.fieldname for f in meta.fields}

    data = {"doctype": "Travel Lead"}

    # Map frontend → doctype fields
    mapping = {
        "lead_name":              ["lead_name", "full_name", "customer_name"],
        "mobile":                 ["mobile_no", "phone", "mobile"],
        "email":                  ["email_id", "email"],
        "interested_destination": ["interested_destination", "destination"],
        "tour_type_pref":         ["tour_type_pref", "tour_type"],
        "travel_month":           ["travel_month"],
        "pax_count":              ["pax_count", "no_of_pax"],
        "budget_per_person":      ["budget_per_person", "budget"],
        "status":                 ["status"],
        "assigned_consultant":    ["assigned_consultant", "lead_owner"],
        "notes":                  ["notes", "remarks"],
        "source":                 ["source"],
    }

    for arg_key, doctype_candidates in mapping.items():
        val = kwargs.get(arg_key)
        if val is None:
            continue
        for candidate in doctype_candidates:
            if candidate in real_fields:
                data[candidate] = val
                break

    try:
        doc = frappe.get_doc(data)
        doc.flags.ignore_permissions = True
        doc.insert()
        frappe.db.commit()
        return {"success": True, "name": doc.name}
    except Exception as e:
        frappe.log_error(str(e), "create_lead error")
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def update_lead(**kwargs):
    _assert_founder()
    lead_id = kwargs.get("lead_id")
    if not lead_id or not frappe.db.exists("Travel Lead", lead_id):
        return {"success": False, "error": "Lead not found."}

    doc = frappe.get_doc("Travel Lead", lead_id)
    meta = frappe.get_meta("Travel Lead")
    real_fields = {f.fieldname for f in meta.fields}

    mapping = {
        "lead_name":              ["lead_name", "full_name"],
        "mobile":                 ["mobile_no", "phone"],
        "email":                  ["email_id", "email"],
        "interested_destination": ["interested_destination", "destination"],
        "tour_type_pref":         ["tour_type_pref", "tour_type"],
        "travel_month":           ["travel_month"],
        "pax_count":              ["pax_count"],
        "budget_per_person":      ["budget_per_person"],
        "status":                 ["status"],
        "assigned_consultant":    ["assigned_consultant", "lead_owner"],
        "notes":                  ["notes", "remarks"],
    }

    for arg_key, candidates in mapping.items():
        val = kwargs.get(arg_key)
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
def delete_record(doctype, record_name):
    _assert_founder()
    type_map = {
        "lead":    "Travel Lead",
        "package": "Tour Package",
        "team":    "Employee",
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


# ── bookings ──────────────────────────────────────────────────────

def _bookings():
    meta = frappe.get_meta("Booking")
    real_fields = {f.fieldname for f in meta.fields}
    real_fields.update({"name", "creation", "modified", "docstatus"})

    want = [
        "name", "customer", "tour_package", "departure_date", "return_date",
        "total_pax", "adult_pax", "child_pax", "room_category",
        "grand_total", "advance_paid", "balance_due", "balance_due_date",
        "payment_status", "booking_status", "sales_consultant",
        "special_requests", "destination", "creation",
        # alternate names
        "lead", "travel_lead", "travel_date", "pax_count",
        "total_amount", "paid_amount", "status",
    ]
    safe = [f for f in want if f in real_fields]

    bookings = frappe.get_all(
        "Booking",
        filters={"docstatus": ["!=", 2]},
        fields=safe,
        order_by="creation desc",
        limit=500,
    )

    pax_meta = frappe.get_meta("Booking Pax")
    pax_real = {f.fieldname for f in pax_meta.fields}

    for b in bookings:
        # Normalize
        b.setdefault("customer", b.get("lead") or b.get("travel_lead") or "")
        b.setdefault("departure_date", b.get("travel_date") or "")
        b.setdefault("total_pax", cint(b.get("pax_count") or b.get("adult_pax") or 0))
        b.setdefault("grand_total", flt(b.get("total_amount") or 0))
        b.setdefault("advance_paid", flt(b.get("paid_amount") or 0))
        b.setdefault("balance_due", flt(b.get("grand_total", 0)) - flt(b.get("advance_paid", 0)))
        b.setdefault("booking_status", b.get("status") or "Draft")
        b.setdefault("payment_status", "Paid" if b.get("balance_due", 0) <= 0 else "Partial")
        b.setdefault("sales_consultant", "")
        b.setdefault("destination", "")
        b.setdefault("room_category", "")

        # Pax details
        pax_want = ["pax_name", "pax_type", "age", "gender", "id_type",
                    "id_number", "passport_expiry", "nationality", "visa_status"]
        pax_safe = [f for f in pax_want if f in pax_real]
        b["pax_details"] = frappe.get_all(
            "Booking Pax", filters={"parent": b["name"]}, fields=pax_safe or ["name"]
        )

    return bookings


@frappe.whitelist()
def create_booking(**kwargs):
    _assert_founder()
    meta = frappe.get_meta("Booking")
    real_fields = {f.fieldname for f in meta.fields}

    grand = flt(kwargs.get("grand_total", 0))
    advance = flt(kwargs.get("advance_paid", 0))
    adults = cint(kwargs.get("adult_pax", 0))
    children = cint(kwargs.get("child_pax", 0))

    data = {"doctype": "Booking"}
    mapping = {
        "customer":          ["customer", "lead", "travel_lead"],
        "tour_package":      ["tour_package", "package"],
        "departure_date":    ["departure_date", "travel_date"],
        "return_date":       ["return_date"],
        "adult_pax":         ["adult_pax"],
        "child_pax":         ["child_pax"],
        "total_pax":         ["total_pax", "pax_count"],
        "room_category":     ["room_category"],
        "grand_total":       ["grand_total", "total_amount"],
        "advance_paid":      ["advance_paid", "paid_amount"],
        "balance_due":       ["balance_due"],
        "balance_due_date":  ["balance_due_date"],
        "sales_consultant":  ["sales_consultant"],
        "booking_status":    ["booking_status", "status"],
        "payment_status":    ["payment_status"],
        "special_requests":  ["special_requests", "remarks"],
        "destination":       ["destination"],
    }

    values = dict(kwargs)
    values["total_pax"]      = adults + children
    values["balance_due"]    = grand - advance
    values["payment_status"] = "Paid" if grand - advance <= 0 else "Partial"

    for k, candidates in mapping.items():
        val = values.get(k)
        if val is None:
            continue
        for c in candidates:
            if c in real_fields:
                data[c] = val
                break

    try:
        doc = frappe.get_doc(data)
        doc.flags.ignore_permissions = True
        doc.insert()
        frappe.db.commit()
        return {"success": True, "name": doc.name}
    except Exception as e:
        frappe.log_error(str(e), "create_booking error")
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def update_booking(**kwargs):
    _assert_founder()
    bid = kwargs.get("booking_id")
    if not frappe.db.exists("Booking", bid):
        return {"success": False, "error": "Booking not found."}

    doc = frappe.get_doc("Booking", bid)
    meta = frappe.get_meta("Booking")
    real_fields = {f.fieldname for f in meta.fields}

    grand   = flt(kwargs.get("grand_total", doc.get("grand_total") or doc.get("total_amount") or 0))
    advance = flt(kwargs.get("advance_paid", doc.get("advance_paid") or doc.get("paid_amount") or 0))

    mapping = {
        "tour_package":     ["tour_package"],
        "departure_date":   ["departure_date", "travel_date"],
        "return_date":      ["return_date"],
        "adult_pax":        ["adult_pax"],
        "child_pax":        ["child_pax"],
        "room_category":    ["room_category"],
        "sales_consultant": ["sales_consultant"],
        "booking_status":   ["booking_status", "status"],
        "special_requests": ["special_requests", "remarks"],
    }

    for k, candidates in mapping.items():
        val = kwargs.get(k)
        if val is None:
            continue
        for c in candidates:
            if c in real_fields:
                setattr(doc, c, val)
                break

    for f in ["grand_total", "total_amount"]:
        if f in real_fields:
            setattr(doc, f, grand)
    for f in ["advance_paid", "paid_amount"]:
        if f in real_fields:
            setattr(doc, f, advance)
    for f in ["balance_due"]:
        if f in real_fields:
            setattr(doc, f, grand - advance)
    for f in ["payment_status"]:
        if f in real_fields:
            setattr(doc, f, "Paid" if grand - advance <= 0 else "Partial")

    adults   = cint(kwargs.get("adult_pax", doc.get("adult_pax") or 0))
    children = cint(kwargs.get("child_pax", doc.get("child_pax") or 0))
    for f in ["total_pax", "pax_count"]:
        if f in real_fields:
            setattr(doc, f, adults + children)

    try:
        doc.flags.ignore_permissions = True
        doc.save()
        frappe.db.commit()
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def update_booking_status(booking_name, status):
    _assert_founder()
    if not frappe.db.exists("Booking", booking_name):
        return {"success": False, "error": "Not found."}
    meta = frappe.get_meta("Booking")
    real_fields = {f.fieldname for f in meta.fields}
    field = "booking_status" if "booking_status" in real_fields else "status"
    frappe.db.set_value("Booking", booking_name, field, status)
    frappe.db.commit()
    return {"success": True}


@frappe.whitelist()
def record_payment(**kwargs):
    _assert_founder()
    bname = kwargs.get("booking_name")
    amount = flt(kwargs.get("amount", 0))
    if not bname or amount <= 0:
        return {"success": False, "error": "Invalid."}
    if not frappe.db.exists("Booking", bname):
        return {"success": False, "error": "Booking not found."}

    doc = frappe.get_doc("Booking", bname)
    meta = frappe.get_meta("Booking")
    real_fields = {f.fieldname for f in meta.fields}

    cur_paid  = flt(doc.get("advance_paid") or doc.get("paid_amount") or 0)
    grand     = flt(doc.get("grand_total") or doc.get("total_amount") or 0)
    new_paid  = cur_paid + amount
    new_bal   = max(0, grand - new_paid)

    for f in ["advance_paid", "paid_amount"]:
        if f in real_fields:
            setattr(doc, f, new_paid)
    for f in ["balance_due"]:
        if f in real_fields:
            setattr(doc, f, new_bal)
    for f in ["payment_status"]:
        if f in real_fields:
            setattr(doc, f, "Paid" if new_bal <= 0 else "Partial")

    doc.flags.ignore_permissions = True
    doc.save()
    doc.add_comment("Comment", text=(
        f"Payment of ₹{amount:,.0f} recorded via {kwargs.get('mode','—')} "
        f"on {kwargs.get('payment_date', '')}. Ref: {kwargs.get('reference','—')}"
    ))
    frappe.db.commit()
    return {"success": True, "new_balance": new_bal}


# ── packages ──────────────────────────────────────────────────────

def _packages():
    meta = frappe.get_meta("Tour Package")
    real_fields = {f.fieldname for f in meta.fields}
    real_fields.update({"name", "creation"})

    want = ["name", "package_name", "destination", "duration", "nights",
            "tour_type", "price_per_person", "status",
            "inclusions", "exclusions", "description",
            # alternate names
            "duration_days", "no_of_nights", "base_price", "package_price"]
    safe = [f for f in want if f in real_fields]

    pkgs = frappe.get_all("Tour Package", fields=safe, order_by="creation desc")

    for p in pkgs:
        p.setdefault("package_name", p.get("name"))
        p.setdefault("duration", cint(p.get("duration_days") or 0))
        p.setdefault("nights", cint(p.get("no_of_nights") or 0))
        p.setdefault("price_per_person", flt(p.get("base_price") or p.get("package_price") or 0))
        p.setdefault("status", "Active")
        p["bookings_count"] = frappe.db.count("Booking", {"tour_package": p["name"], "docstatus": ["!=", 2]})

    return pkgs


@frappe.whitelist()
def save_package(**kwargs):
    _assert_founder()
    pkg_id = kwargs.get("pkg_id")
    meta = frappe.get_meta("Tour Package")
    real_fields = {f.fieldname for f in meta.fields}

    doc = frappe.get_doc("Tour Package", pkg_id) if pkg_id and frappe.db.exists("Tour Package", pkg_id) else frappe.new_doc("Tour Package")

    mapping = {
        "package_name":    ["package_name", "name"],
        "destination":     ["destination"],
        "duration":        ["duration", "duration_days"],
        "nights":          ["nights", "no_of_nights"],
        "tour_type":       ["tour_type"],
        "price_per_person":["price_per_person", "base_price", "package_price"],
        "status":          ["status"],
        "inclusions":      ["inclusions"],
        "exclusions":      ["exclusions"],
        "description":     ["description"],
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
        doc.insert() if doc.is_new() else doc.save()
        frappe.db.commit()
        return {"success": True, "name": doc.name}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ── customers ─────────────────────────────────────────────────────

def _customers():
    # Get unique customers from Booking
    rows = frappe.db.sql("""
        SELECT DISTINCT customer,
               COUNT(*) as total_bookings,
               COALESCE(SUM(COALESCE(grand_total, total_amount, 0)), 0) as total_spent
        FROM `tabBooking`
        WHERE docstatus != 2 AND customer IS NOT NULL AND customer != ''
        GROUP BY customer
        ORDER BY total_bookings DESC
        LIMIT 200
    """, as_dict=True)

    result = []
    for r in rows:
        # Try to get mobile from Travel Lead
        lead_mobile = frappe.db.get_value("Travel Lead", {"lead_name": r.customer}, "mobile_no") or ""
        last = frappe.db.get_value(
            "Booking",
            {"customer": r.customer, "docstatus": ["!=", 2]},
            "destination",
            order_by="departure_date desc",
        )
        result.append({
            "name":           r.customer,
            "customer_name":  r.customer,
            "mobile":         lead_mobile,
            "total_bookings": r.total_bookings,
            "total_spent":    flt(r.total_spent),
            "last_trip":      last or "—",
        })
    return result


# ── team ──────────────────────────────────────────────────────────

def _team():
    if not frappe.db.exists("DocType", "Employee"):
        return []
    try:
        members = frappe.get_all(
            "Employee",
            filters={"status": "Active"},
            fields=["name", "employee_name", "designation", "cell_number", "company_email", "status"],
            order_by="employee_name",
        )
        for m in members:
            m.setdefault("role", m.get("designation") or "Staff")
            m.setdefault("mobile", m.get("cell_number") or "")
            m.setdefault("email", m.get("company_email") or "")
            m["leads_handled"]      = frappe.db.count("Travel Lead", {"assigned_consultant": m["employee_name"]})
            m["bookings_confirmed"] = frappe.db.count("Booking", {"sales_consultant": m["employee_name"], "docstatus": ["!=", 2]})
        return members
    except Exception:
        return []


@frappe.whitelist()
def save_team_member(**kwargs):
    _assert_founder()
    try:
        doc = frappe.new_doc("Employee")
        doc.employee_name = kwargs.get("employee_name")
        doc.designation   = kwargs.get("role", "Sales Consultant")
        doc.cell_number   = kwargs.get("mobile", "")
        doc.company_email = kwargs.get("email", "")
        doc.status        = "Active"
        doc.date_of_joining = frappe.utils.nowdate()
        doc.flags.ignore_permissions = True
        doc.insert()
        frappe.db.commit()
        return {"success": True, "name": doc.name}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ── visa ──────────────────────────────────────────────────────────

@frappe.whitelist()
def update_visa_status(booking_name, pax_name, visa_status):
    _assert_founder()
    pax = frappe.db.get_value("Booking Pax", {"parent": booking_name, "pax_name": pax_name}, "name")
    if pax:
        frappe.db.set_value("Booking Pax", pax, "visa_status", visa_status)
    # Also try Visa Application
    va = frappe.db.get_value("Visa Application", {"booking": booking_name, "pax_name": pax_name}, "name")
    if va:
        frappe.db.set_value("Visa Application", va, "status", visa_status)
    frappe.db.commit()
    return {"success": True}


# ── helper ────────────────────────────────────────────────────────

def _assert_founder():
    if frappe.session.user == "Guest":
        frappe.throw("Not logged in.", frappe.AuthenticationError)
    roles = frappe.get_roles(frappe.session.user)
    if not {"Founder", "System Manager", "Administrator"}.intersection(set(roles)):
        frappe.throw("Access denied.", frappe.PermissionError)
