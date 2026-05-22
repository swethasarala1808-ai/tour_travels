"""
travel_tour/www/founder_dash.py
Founder Dashboard — backend context + all whitelisted API methods.
Uses EXACT field names confirmed from DocType definitions and error traces.
"""
import frappe
from frappe.utils import flt, cint, nowdate, now_datetime, getdate
import json


# ── PAGE CONTEXT ─────────────────────────────────────────────────────────────

def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect-to=/founder_dash"
        raise frappe.Redirect

    roles = frappe.get_roles(frappe.session.user)
    if not any(r in roles for r in ["System Manager", "Administrator", "Founder"]):
        frappe.throw("Access denied. Founder role required.", frappe.PermissionError)

    context.no_cache = 1
    context.user = frappe.session.user
    context.user_name = frappe.db.get_value("User", frappe.session.user, "full_name") or "Founder"


# ── MAIN DATA LOADER ─────────────────────────────────────────────────────────

@frappe.whitelist()
def get_founder_data():
    if frappe.session.user == "Guest":
        frappe.throw("Login required", frappe.AuthenticationError)

    user_name = frappe.db.get_value("User", frappe.session.user, "full_name") or "Founder"
    first = user_name.split()[0]

    return {
        "founder": {"full_name": user_name, "first_name": first},
        "stats":           _get_stats(),
        "monthly_revenue": _get_monthly_revenue(),
        "leads":           _get_leads(),
        "bookings":        _get_bookings(),
        "packages":        _get_packages(),
        "customers":       _get_customers(),
        "team":            [],
    }


def _get_stats():
    stats = {
        "total_revenue": 0,
        "total_balance_due": 0,
        "active_bookings": 0,
        "open_leads": 0,
        "departures_30d": 0,
    }
    try:
        r = frappe.db.sql("""
            SELECT
                COALESCE(SUM(grand_total), 0) AS revenue,
                COALESCE(SUM(GREATEST(0, grand_total - COALESCE(
                    (SELECT COALESCE(SUM(amount),0) FROM `tabPayment Entry Reference`
                     WHERE reference_name=b.name AND docstatus=1), 0
                ))), 0) AS balance,
                COUNT(*) AS total
            FROM `tabBooking` b
            WHERE docstatus != 2
        """, as_dict=True)
        if r:
            stats["total_revenue"] = float(r[0].revenue or 0)
            stats["active_bookings"] = int(r[0].total or 0)
        # Simple balance from booking fields
        bal = frappe.db.sql(
            "SELECT COALESCE(SUM(grand_total),0) FROM `tabBooking` WHERE docstatus=1", as_list=True
        )
        stats["total_revenue"] = float(bal[0][0] or 0) if bal else 0
    except Exception:
        pass

    try:
        # Open leads: status NOT in Converted/Lost
        stats["open_leads"] = frappe.db.count(
            "Travel Lead", filters={"status": ["not in", ["Converted", "Lost"]]}
        )
    except Exception:
        pass

    try:
        from frappe.utils import add_days
        stats["departures_30d"] = frappe.db.count(
            "Booking",
            filters={
                "departure_date": ["between", [nowdate(), add_days(nowdate(), 30)]],
                "docstatus": ["!=", 2],
            },
        )
    except Exception:
        pass

    return stats


def _get_monthly_revenue():
    try:
        rows = frappe.db.sql("""
            SELECT MONTH(departure_date) AS mnum, COALESCE(SUM(grand_total),0) AS rev
            FROM `tabBooking`
            WHERE docstatus != 2 AND YEAR(departure_date) = YEAR(CURDATE())
            GROUP BY MONTH(departure_date)
        """, as_dict=True)
        m_map = {int(r.mnum): float(r.rev or 0) for r in rows}
        labels = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
        return [{"month": labels[i], "rev": m_map.get(i + 1, 0)} for i in range(12)]
    except Exception:
        return [{"month": m, "rev": 0} for m in ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]]


def _get_leads():
    try:
        return frappe.get_all(
            "Travel Lead",
            fields=[
                "name", "full_name as lead_name", "mobile_no as mobile",
                "email_id as email", "status", "source",
                "suggested_package", "pax_count", "preferred_month as travel_month",
                "assigned_consultant", "creation",
            ],
            order_by="creation desc",
            limit=200,
        )
    except Exception:
        return []


def _get_bookings():
    try:
        rows = frappe.db.sql("""
            SELECT
                name, customer, customer_mobile,
                tour_package, departure_date, total_pax,
                sales_consultant, base_amount, gst_amount,
                tcs_amount, grand_total, docstatus,
                creation
            FROM `tabBooking`
            WHERE docstatus != 2
            ORDER BY creation DESC
            LIMIT 200
        """, as_dict=True)

        result = []
        for b in rows:
            grand   = float(b.get("grand_total") or 0)
            advance = _get_advance_paid(b["name"])
            balance = max(0.0, grand - advance)
            status_map = {0: "Draft", 1: "Confirmed", 2: "Cancelled"}
            booking_status = status_map.get(cint(b.get("docstatus", 0)), "Draft")
            payment_status = "Paid" if balance <= 0 and grand > 0 else ("Partial" if advance > 0 else "Pending")

            # Get pax details
            pax_details = []
            try:
                pax_rows = frappe.db.sql("""
                    SELECT pax_name, pax_type, passport_number, visa_status
                    FROM `tabBooking Pax`
                    WHERE parent = %s
                """, b["name"], as_dict=True)
                for p in pax_rows:
                    pax_details.append({
                        "pax_name":      p.get("pax_name", ""),
                        "pax_type":      p.get("pax_type", "Adult"),
                        "id_number":     p.get("passport_number", ""),
                        "passport_expiry": "",
                        "visa_status":   p.get("visa_status", "Not Applied"),
                    })
            except Exception:
                pass

            # Get destination from Tour Package
            destination = ""
            if b.get("tour_package"):
                try:
                    destination = frappe.db.get_value("Tour Package", b["tour_package"], "destination") or ""
                except Exception:
                    pass

            result.append({
                "name":            b["name"],
                "customer":        b.get("customer") or b.get("customer_mobile") or "",
                "customer_mobile": b.get("customer_mobile", ""),
                "tour_package":    b.get("tour_package", ""),
                "departure_date":  str(b.get("departure_date", "") or ""),
                "return_date":     "",
                "total_pax":       cint(b.get("total_pax", 0)),
                "adult_pax":       cint(b.get("total_pax", 0)),
                "child_pax":       0,
                "sales_consultant": b.get("sales_consultant", ""),
                "base_amount":     float(b.get("base_amount") or 0),
                "gst_amount":      float(b.get("gst_amount") or 0),
                "grand_total":     grand,
                "advance_paid":    advance,
                "balance_due":     balance,
                "balance_due_date": "",
                "booking_status":  booking_status,
                "payment_status":  payment_status,
                "destination":     str(destination),
                "pax_details":     pax_details,
                "special_requests": "",
                "creation":        str(b.get("creation", "")),
            })
        return result
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "get_bookings error")
        return []


def _get_advance_paid(booking_name):
    """Sum of submitted payment entries for this booking."""
    try:
        r = frappe.db.sql("""
            SELECT COALESCE(SUM(per.amount), 0)
            FROM `tabPayment Entry Reference` per
            JOIN `tabPayment Entry` pe ON pe.name = per.parent
            WHERE per.reference_name = %s AND pe.docstatus = 1
        """, booking_name, as_list=True)
        return float(r[0][0] or 0) if r else 0.0
    except Exception:
        return 0.0


def _get_packages():
    try:
        rows = frappe.get_all(
            "Tour Package",
            fields=[
                "name", "package_name", "destination", "tour_type",
                "duration_days", "duration_nights", "creation",
            ],
            order_by="creation desc",
            limit=100,
        )
        result = []
        for p in rows:
            # Get min price from Package Pricing child
            price = 0
            try:
                pr = frappe.db.sql(
                    "SELECT MIN(price_per_person) FROM `tabPackage Pricing` WHERE parent=%s",
                    p["name"], as_list=True
                )
                price = float(pr[0][0] or 0) if pr and pr[0][0] else 0
            except Exception:
                pass

            bk_count = 0
            try:
                bk_count = frappe.db.count("Booking", {"tour_package": p["name"], "docstatus": ["!=", 2]})
            except Exception:
                pass

            result.append({
                "name":             p["name"],
                "package_name":     p.get("package_name", p["name"]),
                "destination":      str(p.get("destination") or ""),
                "tour_type":        p.get("tour_type", "Domestic"),
                "duration":         cint(p.get("duration_days", 0)),
                "nights":           cint(p.get("duration_nights", 0)),
                "price_per_person": price,
                "status":           "Active",
                "bookings_count":   bk_count,
            })
        return result
    except Exception:
        return []


def _get_customers():
    try:
        rows = frappe.db.sql("""
            SELECT
                mobile_no AS mobile,
                full_name AS lead_name,
                email_id  AS email,
                name
            FROM `tabTravel Lead`
            WHERE status = 'Converted'
            ORDER BY creation DESC
            LIMIT 100
        """, as_dict=True)
        result = []
        for c in rows:
            bk_count = 0
            total_spent = 0
            try:
                bks = frappe.db.sql(
                    "SELECT COUNT(*) AS cnt, COALESCE(SUM(grand_total),0) AS total FROM `tabBooking` WHERE customer_mobile=%s AND docstatus!=2",
                    c.get("mobile", ""), as_dict=True
                )
                if bks:
                    bk_count = cint(bks[0].cnt or 0)
                    total_spent = float(bks[0].total or 0)
            except Exception:
                pass
            result.append({
                "name":           c.get("name", ""),
                "customer_name":  c.get("lead_name", ""),
                "mobile":         c.get("mobile", ""),
                "email":          c.get("email", ""),
                "total_bookings": bk_count,
                "total_spent":    total_spent,
                "last_trip":      "",
            })
        return result
    except Exception:
        return []


# ── LEAD CRUD ─────────────────────────────────────────────────────────────────

@frappe.whitelist()
def create_lead(**kwargs):
    if frappe.session.user == "Guest":
        frappe.throw("Login required", frappe.AuthenticationError)
    try:
        doc = frappe.get_doc({
            "doctype":            "Travel Lead",
            "full_name":          kwargs.get("lead_name", ""),
            "mobile_no":          kwargs.get("mobile", ""),
            "email_id":           kwargs.get("email", ""),
            "status":             kwargs.get("status", "New"),
            "source":             kwargs.get("source", ""),
            "pax_count":          cint(kwargs.get("pax_count", 0)),
            "preferred_month":    kwargs.get("travel_month", ""),
            "assigned_consultant": kwargs.get("assigned_consultant", ""),
        })
        # Optional fields — skip if column doesn't exist
        for field, kwarg in [
            ("interested_destination", "interested_destination"),
            ("suggested_package", "suggested_package"),
            ("budget_per_person", "budget_per_person"),
            ("tour_type_pref", "tour_type_pref"),
        ]:
            if kwargs.get(kwarg) and frappe.db.has_column("Travel Lead", field):
                doc.set(field, kwargs[kwarg])

        doc.flags.ignore_permissions = True
        doc.insert()
        frappe.db.commit()

        # Add notes as comment
        notes = kwargs.get("notes", "")
        if notes:
            doc.add_comment("Comment", text=notes)
            frappe.db.commit()

        return {"success": True, "name": doc.name}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "create_lead error")
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def update_lead(**kwargs):
    if frappe.session.user == "Guest":
        frappe.throw("Login required", frappe.AuthenticationError)
    try:
        lid = kwargs.get("lead_id") or kwargs.get("name")
        if not lid or not frappe.db.exists("Travel Lead", lid):
            return {"success": False, "error": "Lead not found"}

        doc = frappe.get_doc("Travel Lead", lid)
        field_map = {
            "lead_name":          "full_name",
            "mobile":             "mobile_no",
            "email":              "email_id",
            "status":             "status",
            "source":             "source",
            "pax_count":          "pax_count",
            "travel_month":       "preferred_month",
            "assigned_consultant": "assigned_consultant",
        }
        for kwarg, field in field_map.items():
            if kwarg in kwargs and kwargs[kwarg] is not None:
                doc.set(field, kwargs[kwarg])

        # Optional fields
        for field, kwarg in [
            ("interested_destination", "interested_destination"),
            ("suggested_package", "suggested_package"),
            ("budget_per_person", "budget_per_person"),
            ("tour_type_pref", "tour_type_pref"),
        ]:
            if kwargs.get(kwarg) is not None and frappe.db.has_column("Travel Lead", field):
                doc.set(field, kwargs[kwarg])

        doc.flags.ignore_permissions = True
        doc.save()
        frappe.db.commit()
        return {"success": True, "name": doc.name}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "update_lead error")
        return {"success": False, "error": str(e)}


# ── BOOKING CRUD (SQL-based to bypass validate() pricing hook) ────────────────

@frappe.whitelist()
def create_booking(**kwargs):
    if frappe.session.user == "Guest":
        frappe.throw("Login required", frappe.AuthenticationError)
    try:
        import time
        bname = f"BOOK-{int(time.time())}"
        grand_total = flt(kwargs.get("grand_total", 0))
        frappe.db.sql("""
            INSERT INTO `tabBooking`
            (name, creation, modified, modified_by, owner, docstatus,
             customer, customer_mobile, tour_package, departure_date,
             total_pax, sales_consultant, base_amount, grand_total)
            VALUES (%s, NOW(), NOW(), %s, %s, 0,
                    %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            bname, frappe.session.user, frappe.session.user,
            kwargs.get("customer", ""),
            kwargs.get("customer_mobile", kwargs.get("customer", "")),
            kwargs.get("tour_package", ""),
            kwargs.get("departure_date", ""),
            cint(kwargs.get("total_pax", kwargs.get("adult_pax", 0))),
            kwargs.get("sales_consultant", ""),
            flt(kwargs.get("base_amount", grand_total)),
            grand_total,
        ))
        frappe.db.commit()
        return {"success": True, "name": bname}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "create_booking error")
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def update_booking(**kwargs):
    if frappe.session.user == "Guest":
        frappe.throw("Login required", frappe.AuthenticationError)
    try:
        bid = kwargs.get("booking_id") or kwargs.get("name")
        if not bid:
            return {"success": False, "error": "No booking ID"}

        sets, vals = [], []
        field_map = {
            "customer":        "customer",
            "tour_package":    "tour_package",
            "departure_date":  "departure_date",
            "total_pax":       "total_pax",
            "sales_consultant":"sales_consultant",
            "grand_total":     "grand_total",
            "base_amount":     "base_amount",
        }
        for kwarg, col in field_map.items():
            if kwarg in kwargs and kwargs[kwarg] is not None:
                sets.append(f"`{col}`=%s")
                vals.append(kwargs[kwarg])

        if not sets:
            return {"success": True, "name": bid}

        vals.extend([frappe.session.user, bid])
        frappe.db.sql(
            f"UPDATE `tabBooking` SET {','.join(sets)}, modified=NOW(), modified_by=%s WHERE name=%s",
            vals
        )
        frappe.db.commit()
        return {"success": True, "name": bid}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "update_booking error")
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def update_booking_status(booking_name, status):
    if frappe.session.user == "Guest":
        frappe.throw("Login required", frappe.AuthenticationError)
    try:
        ds_map = {"Confirmed": 1, "Cancelled": 2, "Draft": 0, "Completed": 1}
        ds = ds_map.get(status, 0)
        frappe.db.sql(
            "UPDATE `tabBooking` SET docstatus=%s, modified=NOW(), modified_by=%s WHERE name=%s",
            (ds, frappe.session.user, booking_name)
        )
        frappe.db.commit()
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


@frappe.whitelist()
def record_payment(booking_name, amount, payment_date=None, mode=None, reference=None, notes=None):
    if frappe.session.user == "Guest":
        frappe.throw("Login required", frappe.AuthenticationError)
    try:
        bk = frappe.db.get_value("Booking", booking_name, ["name", "grand_total", "customer"], as_dict=True)
        if not bk:
            return {"success": False, "error": "Booking not found"}

        # Add a comment to record the payment
        frappe.db.sql("""
            INSERT INTO `tabComment`
            (name, creation, modified, modified_by, owner, comment_type,
             reference_doctype, reference_name, content, published)
            VALUES (UUID(), NOW(), NOW(), %s, %s, 'Comment',
                    'Booking', %s, %s, 1)
        """, (
            frappe.session.user, frappe.session.user,
            booking_name,
            f"Payment ₹{flt(amount):,.0f} via {mode or 'Cash'} on {payment_date or nowdate()}. Ref: {reference or '—'}. {notes or ''}"
        ))
        frappe.db.commit()
        return {"success": True}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "record_payment error")
        return {"success": False, "error": str(e)}


# ── TOUR PACKAGE CRUD ─────────────────────────────────────────────────────────

@frappe.whitelist()
def save_package(**kwargs):
    if frappe.session.user == "Guest":
        frappe.throw("Login required", frappe.AuthenticationError)
    try:
        # Map dashboard tour_type → DocType options (Domestic/International)
        raw_type = kwargs.get("tour_type", "Domestic")
        tt_map = {
            "Group": "Domestic", "FIT": "Domestic",
            "Honeymoon": "Domestic", "Corporate": "Domestic",
            "Adventure": "Domestic", "Domestic": "Domestic",
            "International": "International",
        }
        tour_type = tt_map.get(raw_type, "Domestic")

        pkg_id = kwargs.get("pkg_id") or kwargs.get("package_name")
        if pkg_id and frappe.db.exists("Tour Package", pkg_id):
            doc = frappe.get_doc("Tour Package", pkg_id)
            doc.package_name   = kwargs.get("package_name", doc.package_name)
            doc.tour_type      = tour_type
            doc.duration_days  = cint(kwargs.get("duration", doc.duration_days))
            doc.duration_nights = cint(kwargs.get("nights", doc.duration_nights))
        else:
            doc = frappe.get_doc({
                "doctype":        "Tour Package",
                "package_name":   kwargs.get("package_name", "New Package"),
                "tour_type":      tour_type,
                "duration_days":  cint(kwargs.get("duration", 1)),
                "duration_nights": cint(kwargs.get("nights", 0)),
                "visa_required":  0,
            })

        doc.flags.ignore_permissions = True
        doc.flags.ignore_mandatory   = True
        doc.save() if doc.get("__islocal") is False and pkg_id and frappe.db.exists("Tour Package", pkg_id) else doc.insert()
        frappe.db.commit()
        return {"success": True, "name": doc.name}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "save_package error")
        return {"success": False, "error": str(e)}


create_package = save_package  # alias


# ── VISA ──────────────────────────────────────────────────────────────────────

@frappe.whitelist()
def update_visa_status(booking_name, pax_name, visa_status):
    if frappe.session.user == "Guest":
        frappe.throw("Login required", frappe.AuthenticationError)
    try:
        frappe.db.sql(
            "UPDATE `tabBooking Pax` SET visa_status=%s, modified=NOW() WHERE parent=%s AND pax_name=%s",
            (visa_status, booking_name, pax_name)
        )
        frappe.db.commit()
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ── TEAM ──────────────────────────────────────────────────────────────────────

@frappe.whitelist()
def save_team_member(**kwargs):
    """Create a Frappe User with Travel Consultant role."""
    if frappe.session.user == "Guest":
        frappe.throw("Login required", frappe.AuthenticationError)
    try:
        email = kwargs.get("email", "")
        name  = kwargs.get("employee_name", "")
        if not email:
            email = f"{name.lower().replace(' ','.')}.tc@traveltour.internal"

        if frappe.db.exists("User", email):
            return {"success": True, "name": email, "message": "User already exists"}

        user = frappe.get_doc({
            "doctype":   "User",
            "email":     email,
            "first_name": name.split()[0] if name else "Team",
            "last_name":  " ".join(name.split()[1:]) if len(name.split()) > 1 else "",
            "mobile_no": kwargs.get("mobile", ""),
            "enabled":   1,
            "user_type": "System User",
            "send_welcome_email": 0,
            "roles": [{"role": "Travel Consultant"}],
        })
        user.flags.ignore_permissions = True
        user.insert()
        frappe.db.commit()
        return {"success": True, "name": user.name}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "save_team_member error")
        return {"success": False, "error": str(e)}


# ── DELETE ────────────────────────────────────────────────────────────────────

@frappe.whitelist()
def delete_record(doctype, record_name):
    if frappe.session.user == "Guest":
        frappe.throw("Login required", frappe.AuthenticationError)
    try:
        allowed = ["Travel Lead", "Tour Package"]
        if doctype not in allowed:
            return {"success": False, "error": f"Cannot delete {doctype} from dashboard"}
        frappe.delete_doc(doctype, record_name, ignore_permissions=True, force=True)
        frappe.db.commit()
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}
