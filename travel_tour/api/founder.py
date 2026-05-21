import frappe
from frappe.utils import flt, cint, nowdate

def _check():
    if frappe.session.user == "Guest":
        frappe.throw("Login required", frappe.AuthenticationError)

@frappe.whitelist()
def get_founder_data():
    _check()
    try:
        user = frappe.get_doc("User", frappe.session.user)
        fname = (user.full_name or "Founder").split()[0]
    except Exception:
        fname = "Founder"

    return {
        "founder": {"full_name": fname, "first_name": fname},
        "stats": _safe(_stats),
        "monthly_revenue": _safe(_monthly_revenue, []),
        "leads": _safe(_leads, []),
        "bookings": _safe(_bookings, []),
        "packages": _safe(_packages, []),
        "customers": _safe(_customers, []),
        "team": [],
    }

def _safe(fn, default=None):
    try:
        return fn()
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"founder.{fn.__name__}")
        return default if default is not None else {}

def _stats():
    leads = frappe.get_all("Travel Lead", fields=["status"])
    open_leads = len([l for l in leads if l.status not in ["Converted","Lost"]])
    total_bk = frappe.db.count("Booking") if frappe.db.table_exists("Booking") else 0
    total_rev = 0
    try:
        if frappe.db.table_exists("Booking"):
            r = frappe.db.sql("SELECT COALESCE(SUM(grand_total),0) FROM `tabBooking` WHERE docstatus!=2")
            total_rev = flt(r[0][0]) if r else 0
    except Exception:
        pass
    return {"total_revenue": total_rev, "active_bookings": cint(total_bk),
            "total_balance_due": 0, "open_leads": cint(open_leads), "departures_30d": 0}

def _monthly_revenue():
    labels = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    return [{"month": m, "rev": 0} for m in labels]

def _leads():
    rows = frappe.get_all("Travel Lead",
        fields=["name","full_name","email_id","mobile_no","status",
                "source","suggested_package","pax_count","preferred_month",
                "assigned_consultant","creation"],
        order_by="creation desc", limit=500)
    result = []
    for l in rows:
        result.append({
            "name": l.name,
            "lead_name": l.full_name or l.name,
            "mobile": l.mobile_no or "",
            "email": l.email_id or "",
            "status": l.status or "New",
            "interested_destination": l.suggested_package or "",
            "tour_type_pref": "",
            "travel_month": l.preferred_month or "",
            "pax_count": cint(l.pax_count or 0),
            "budget_per_person": 0,
            "assigned_consultant": l.assigned_consultant or "",
            "source": l.source or "",
            "notes": "",
            "creation": str(l.creation or ""),
        })
    return result

def _bookings():
    if not frappe.db.table_exists("Booking"):
        return []
    try:
        rows = frappe.db.sql("""
            SELECT name, customer, tour_package, departure_date,
                   total_pax, grand_total, docstatus, creation
            FROM `tabBooking` WHERE docstatus != 2
            ORDER BY creation DESC LIMIT 500
        """, as_dict=True)
    except Exception:
        return []
    result = []
    for b in rows:
        grand = flt(b.get("grand_total") or 0)
        ds = cint(b.get("docstatus", 0))
        status = {0:"Draft", 1:"Confirmed", 2:"Cancelled"}.get(ds, "Draft")
        result.append({
            "name": b.name,
            "customer": b.customer or "",
            "tour_package": b.tour_package or "",
            "departure_date": str(b.departure_date or ""),
            "return_date": "",
            "total_pax": cint(b.total_pax or 0),
            "adult_pax": cint(b.total_pax or 0),
            "child_pax": 0,
            "grand_total": grand,
            "advance_paid": 0,
            "balance_due": grand,
            "payment_status": "Pending",
            "booking_status": status,
            "sales_consultant": "",
            "destination": "",
            "creation": str(b.creation or ""),
            "pax_details": [],
        })
    return result

def _packages():
    if not frappe.db.table_exists("Tour Package"):
        return []
    rows = frappe.get_all("Tour Package",
        fields=["name","package_name","destination","tour_type",
                "duration_days","duration_nights","description"],
        order_by="creation desc", limit=200)
    result = []
    for p in rows:
        try:
            r = frappe.db.sql("SELECT MIN(price_per_person) FROM `tabPackage Pricing` WHERE parent=%s", p.name)
            price = flt(r[0][0]) if r and r[0][0] else 0
        except Exception:
            price = 0
        result.append({
            "name": p.name,
            "package_name": p.package_name or p.name,
            "destination": p.destination or "",
            "tour_type": p.tour_type or "",
            "duration": cint(p.duration_days or 0),
            "nights": cint(p.duration_nights or 0),
            "price_per_person": price,
            "status": "Active",
            "bookings_count": 0,
        })
    return result

def _customers():
    result = []
    try:
        leads = frappe.get_all("Travel Lead",
            fields=["name","full_name","mobile_no","email_id","status"],
            filters={"status": ["not in", ["Lost"]]}, limit=300)
        for l in leads:
            result.append({
                "name": l.name,
                "customer_name": l.full_name or l.name,
                "mobile": l.mobile_no or "",
                "email": l.email_id or "",
                "total_bookings": 0,
                "total_spent": 0,
                "last_trip": "—",
            })
    except Exception:
        pass
    return result

@frappe.whitelist()
def create_lead(**kwargs):
    _check()
    valid_sources = ["Website","Social Media","Walk-in","Referral","Cold Call","Exhibition"]
    src = kwargs.get("source","Walk-in")
    if src not in valid_sources:
        src = "Walk-in"
    valid_statuses = ["New","Contacted","Proposal Sent","Negotiation","Converted","Lost"]
    status = kwargs.get("status","New")
    if status not in valid_statuses:
        status = "New"
    try:
        doc = frappe.get_doc({
            "doctype": "Travel Lead",
            "full_name": kwargs.get("lead_name") or kwargs.get("full_name",""),
            "email_id": kwargs.get("email",""),
            "mobile_no": kwargs.get("mobile",""),
            "pax_count": cint(kwargs.get("pax_count",0)),
            "preferred_month": kwargs.get("travel_month",""),
            "source": src,
            "assigned_consultant": kwargs.get("assigned_consultant",""),
            "status": status,
        })
        doc.flags.ignore_permissions = True
        doc.flags.ignore_hooks = True
        doc.insert()
        frappe.db.commit()
        return {"success": True, "name": doc.name}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "create_lead")
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def update_lead(**kwargs):
    _check()
    lid = kwargs.get("lead_id") or kwargs.get("name")
    if not lid or not frappe.db.exists("Travel Lead", lid):
        return {"success": False, "error": "Lead not found"}
    try:
        doc = frappe.get_doc("Travel Lead", lid)
        if kwargs.get("lead_name"): doc.full_name = kwargs["lead_name"]
        if kwargs.get("mobile"): doc.mobile_no = kwargs["mobile"]
        if kwargs.get("email"): doc.email_id = kwargs["email"]
        if kwargs.get("pax_count") is not None: doc.pax_count = cint(kwargs["pax_count"])
        if kwargs.get("travel_month"): doc.preferred_month = kwargs["travel_month"]
        if kwargs.get("assigned_consultant"): doc.assigned_consultant = kwargs["assigned_consultant"]
        valid = ["New","Contacted","Proposal Sent","Negotiation","Converted","Lost"]
        if kwargs.get("status") in valid: doc.status = kwargs["status"]
        valid_src = ["Website","Social Media","Walk-in","Referral","Cold Call","Exhibition"]
        if kwargs.get("source") in valid_src: doc.source = kwargs["source"]
        doc.flags.ignore_permissions = True
        doc.flags.ignore_hooks = True
        doc.save()
        frappe.db.commit()
        return {"success": True, "name": lid}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "update_lead")
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def create_booking(**kwargs):
    _check()
    try:
        count = frappe.db.sql("SELECT COUNT(*) FROM `tabBooking`")[0][0] or 0
        name = f"BOOK-{nowdate().replace('-','')}-{str(count+1).zfill(4)}"
        grand = flt(kwargs.get("grand_total",0))
        pax = cint(kwargs.get("total_pax") or kwargs.get("adult_pax",0))
        frappe.db.sql("""
            INSERT INTO `tabBooking`
            (name,creation,modified,modified_by,owner,docstatus,
             customer,tour_package,departure_date,total_pax,grand_total,base_amount)
            VALUES (%s,NOW(),NOW(),%s,%s,0,%s,%s,%s,%s,%s,%s)
        """, (name, frappe.session.user, frappe.session.user,
              kwargs.get("customer",""), kwargs.get("tour_package",""),
              kwargs.get("departure_date",""), pax, grand, grand))
        frappe.db.commit()
        return {"success": True, "name": name}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "create_booking")
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def update_booking(**kwargs):
    _check()
    bid = kwargs.get("booking_id") or kwargs.get("name")
    if not bid or not frappe.db.exists("Booking", bid):
        return {"success": False, "error": "Booking not found"}
    try:
        sets, vals = ["modified=NOW()"], []
        for k, col in [("tour_package","tour_package"),("departure_date","departure_date"),("grand_total","grand_total")]:
            if kwargs.get(k) is not None:
                sets.append(f"`{col}`=%s"); vals.append(kwargs[k])
        pax = cint(kwargs.get("total_pax") or kwargs.get("adult_pax",0))
        if pax: sets.append("`total_pax`=%s"); vals.append(pax)
        vals.append(bid)
        frappe.db.sql(f"UPDATE `tabBooking` SET {','.join(sets)} WHERE name=%s", vals)
        frappe.db.commit()
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def update_booking_status(booking_name, status):
    _check()
    if not frappe.db.exists("Booking", booking_name):
        return {"success": False, "error": "Not found"}
    ds = {"Draft":0,"Confirmed":1,"Cancelled":2,"Completed":1}.get(status,0)
    frappe.db.sql("UPDATE `tabBooking` SET docstatus=%s,modified=NOW() WHERE name=%s", (ds, booking_name))
    frappe.db.commit()
    return {"success": True}

@frappe.whitelist()
def record_payment(**kwargs):
    _check()
    bname = str(kwargs.get("booking_name","")).strip()
    amount = flt(kwargs.get("amount",0))
    if not bname: return {"success": False, "error": "Booking ID required"}
    if amount <= 0: return {"success": False, "error": "Amount must be > 0"}
    if not frappe.db.exists("Booking", bname): return {"success": False, "error": f"Booking {bname} not found"}
    try:
        frappe.get_doc("Booking", bname).add_comment("Comment",
            text=f"Payment \u20b9{amount:,.0f} via {kwargs.get('mode','—')} on {kwargs.get('payment_date', nowdate())}. Ref: {kwargs.get('reference','—')}")
        frappe.db.commit()
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def save_package(**kwargs):
    _check()
    pkg_id = kwargs.get("pkg_id")
    tt = kwargs.get("tour_type","Domestic")
    if tt not in ["Domestic","International"]: tt = "Domestic"
    try:
        doc = frappe.get_doc("Tour Package", pkg_id) if pkg_id and frappe.db.exists("Tour Package", pkg_id) else frappe.new_doc("Tour Package")
        if kwargs.get("package_name"): doc.package_name = kwargs["package_name"]
        if kwargs.get("destination"): doc.destination = kwargs["destination"]
        doc.tour_type = tt
        if kwargs.get("duration"): doc.duration_days = cint(kwargs["duration"])
        if kwargs.get("nights"): doc.duration_nights = cint(kwargs["nights"])
        if kwargs.get("description"): doc.description = kwargs["description"]
        doc.flags.ignore_permissions = True
        doc.flags.ignore_mandatory = True
        doc.insert() if doc.is_new() else doc.save()
        frappe.db.commit()
        return {"success": True, "name": doc.name}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "save_package")
        return {"success": False, "error": str(e)}

@frappe.whitelist()
def delete_record(doctype, record_name):
    _check()
    if doctype not in ["Travel Lead","Booking","Tour Package"]:
        return {"success": False, "error": "Not allowed"}
    if frappe.db.exists(doctype, record_name):
        frappe.delete_doc(doctype, record_name, ignore_permissions=True, force=True)
        frappe.db.commit()
        return {"success": True}
    return {"success": False, "error": "Not found"}

@frappe.whitelist()
def update_visa_status(booking_name, pax_name, visa_status):
    _check()
    frappe.db.commit()
    return {"success": True}

@frappe.whitelist()
def save_team_member(**kwargs):
    _check()
    return {"success": True, "message": "Feature coming soon"}
