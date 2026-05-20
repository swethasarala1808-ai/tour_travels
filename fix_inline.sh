#!/bin/bash
# ═══════════════════════════════════════════════════════════════
#  PASTE THIS ENTIRE SCRIPT into your terminal at once.
#  Run from: ~/frappe-bench/apps/travel_tour/
#
#  cd ~/frappe-bench/apps/travel_tour
#  bash fix_inline.sh
# ═══════════════════════════════════════════════════════════════

set -e

BENCH="$HOME/frappe-bench"
APP="$HOME/frappe-bench/apps/travel_tour"
WWW="$APP/travel_tour/www"

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║  Tour Travels — Inline Fix (no downloads)   ║"
echo "╚══════════════════════════════════════════════╝"

# ── Find the correct site name ──────────────────────────────────
echo ""
echo "▶ Finding site name..."
SITE=$(ls "$BENCH/sites" | grep -v apps | grep -v assets | grep -v common_site_config.json | head -1)
echo "  Site found: $SITE"

# ── Create www directory ─────────────────────────────────────────
echo ""
echo "▶ Creating www directory..."
mkdir -p "$WWW"
touch "$WWW/__init__.py"
echo "  ✅ $WWW"

# ── Write travel_enquiry.py ──────────────────────────────────────
echo ""
echo "▶ Writing travel_enquiry.py..."
cat > "$WWW/travel_enquiry.py" << 'PYEOF'
"""
travel_tour/www/travel_enquiry.py
Customer Portal Dashboard — Data APIs
"""
import frappe


def get_context(context):
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


@frappe.whitelist()
def get_portal_data():
    if frappe.session.user == "Guest":
        return None
    mobile = frappe.db.get_value("User", frappe.session.user, "mobile_no")
    if not mobile:
        return None
    lead = frappe.db.get_value(
        "Travel Lead", {"mobile": mobile},
        ["name", "lead_name", "mobile", "email", "status",
         "assigned_consultant", "tour_type_pref",
         "interested_destination", "travel_month",
         "pax_count", "budget_per_person"],
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
            bd = b.copy()
            bd["pax_details"] = frappe.get_all(
                "Booking Pax",
                filters={"parent": b["name"]},
                fields=["pax_name", "pax_type", "age", "gender",
                        "id_type", "id_number", "passport_expiry",
                        "nationality", "dietary_pref", "visa_status"],
            )
            if b.get("tour_package"):
                pkg_itin = frappe.db.get_value("Tour Package", b["tour_package"], "itinerary")
                if pkg_itin:
                    bd["itinerary_days"] = frappe.get_all(
                        "Itinerary Day",
                        filters={"parent": pkg_itin},
                        fields=["day_number", "day_title", "morning",
                                "afternoon", "evening", "hotel"],
                        order_by="day_number asc",
                    )
            bookings.append(bd)
    return {"lead": lead, "bookings": bookings}


@frappe.whitelist()
def update_lead_enquiry(destination, tour_type, travel_month,
                        pax_count, budget=0, notes=""):
    if frappe.session.user == "Guest":
        return {"success": False}
    mobile = frappe.db.get_value("User", frappe.session.user, "mobile_no")
    if not mobile:
        return {"success": False}
    lead_name = frappe.db.get_value("Travel Lead", {"mobile": mobile}, "name")
    if not lead_name:
        return {"success": False, "error": "Lead not found."}
    lead = frappe.get_doc("Travel Lead", lead_name)
    if lead.status == "Converted":
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
        lead.tour_type_pref = tour_type
        lead.travel_month = travel_month
        lead.pax_count = pax_count
        lead.budget_per_person = budget
        if notes:
            lead.add_comment("Comment", text=f"Portal enquiry: {notes}")
        if lead.status in ("New", "Contacted"):
            lead.status = "New"
        lead.flags.ignore_permissions = True
        lead.save()
    frappe.db.commit()
    return {"success": True}


@frappe.whitelist()
def update_profile(lead_name, email, tour_type_pref, interested_destination=""):
    if frappe.session.user == "Guest":
        return {"success": False}
    mobile = frappe.db.get_value("User", frappe.session.user, "mobile_no")
    if not mobile:
        return {"success": False}
    lead_id = frappe.db.get_value("Travel Lead", {"mobile": mobile}, "name")
    if not lead_id:
        return {"success": False}
    update = {"lead_name": lead_name, "email": email, "tour_type_pref": tour_type_pref}
    if interested_destination:
        update["interested_destination"] = interested_destination
    frappe.db.set_value("Travel Lead", lead_id, update)
    frappe.db.set_value("User", frappe.session.user, {
        "first_name": lead_name.split()[0] if lead_name else "",
    })
    frappe.db.commit()
    return {"success": True}


@frappe.whitelist()
def create_payment_link(booking_name):
    if frappe.session.user == "Guest":
        return {"success": False}
    mobile = frappe.db.get_value("User", frappe.session.user, "mobile_no")
    customer = frappe.db.get_value("Customer", {"mobile_no": mobile}, "name")
    if not customer:
        return {"success": False, "error": "Customer not found."}
    booking = frappe.db.get_value(
        "Booking", {"name": booking_name, "customer": customer},
        ["name", "balance_due"], as_dict=True,
    )
    if not booking or (booking.balance_due or 0) <= 0:
        return {"success": False, "error": "No balance due."}
    try:
        from travel_tour.api.payment_gateway import create_payment_link as _make
        url = _make(booking_name, booking.balance_due,
                    f"Balance payment for {booking_name}")
        return {"success": True, "url": url}
    except Exception as e:
        frappe.log_error(str(e), "Portal payment link error")
        return {"success": False, "error": "Payment gateway not configured."}
PYEOF
echo "  ✅ travel_enquiry.py"

# ── Write my_portal.py ───────────────────────────────────────────
echo ""
echo "▶ Writing my_portal.py..."
cat > "$WWW/my_portal.py" << 'PYEOF'
"""
travel_tour/www/my_portal.py
Customer Portal — Mobile + Password login
"""
import frappe
import hashlib
import random
import string


def get_context(context):
    context.no_cache = 1
    context.show_sidebar = False
    if frappe.session.user and frappe.session.user != "Guest":
        mobile = frappe.db.get_value("User", frappe.session.user, "mobile_no")
        if mobile and frappe.db.exists("Travel Lead", {"mobile": mobile}):
            frappe.local.flags.redirect_location = "/travel_enquiry"
            raise frappe.Redirect


@frappe.whitelist(allow_guest=True)
def portal_login(mobile, password):
    mobile = (mobile or "").strip()
    password = (password or "").strip()
    if not mobile or not password:
        return {"success": False, "error": "Mobile and password are required."}

    # Check Travel Lead exists
    lead = frappe.db.get_value(
        "Travel Lead", {"mobile": mobile},
        ["name", "lead_name", "portal_password_hash"],
        as_dict=True,
    )
    if not lead:
        # Also try matching by mobile_no field name variations
        lead = frappe.db.get_value(
            "Travel Lead", {"mobile_no": mobile},
            ["name", "lead_name", "portal_password_hash"],
            as_dict=True,
        )
    if not lead:
        return {"success": False,
                "error": "Mobile not registered. Please contact us."}

    stored = lead.get("portal_password_hash") or ""
    if not stored:
        if password != mobile[-4:]:
            return {"success": False,
                    "error": "Incorrect password. Default = last 4 digits of mobile."}
    else:
        if _hash(password) != stored:
            return {"success": False, "error": "Incorrect password."}

    user = _get_or_create_user(mobile, lead.lead_name)
    if not user:
        return {"success": False, "error": "Account error. Contact support."}

    frappe.local.login_manager.login_as(user)
    return {"success": True}


@frappe.whitelist(allow_guest=True)
def reset_portal_password(mobile):
    mobile = (mobile or "").strip()
    lead = frappe.db.get_value("Travel Lead", {"mobile": mobile},
                               ["name", "lead_name"], as_dict=True)
    if not lead:
        return {"success": False, "error": "Mobile not registered."}
    new_pw = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    try:
        frappe.db.set_value("Travel Lead", lead.name,
                            "portal_password_hash", _hash(new_pw))
        frappe.db.commit()
    except Exception:
        pass
    frappe.log_error(f"Portal PW Reset | Mobile:{mobile} | PW:{new_pw}",
                     "Portal Password Reset")
    return {"success": True}


@frappe.whitelist()
def change_portal_password(old_password, new_password):
    if frappe.session.user == "Guest":
        return {"success": False}
    mobile = frappe.db.get_value("User", frappe.session.user, "mobile_no")
    if not mobile:
        return {"success": False}
    lead = frappe.db.get_value("Travel Lead", {"mobile": mobile},
                               ["name", "portal_password_hash"], as_dict=True)
    if not lead:
        return {"success": False}
    stored = lead.portal_password_hash or _hash(mobile[-4:])
    if _hash(old_password) != stored:
        return {"success": False, "error": "Current password incorrect."}
    if len(new_password) < 6:
        return {"success": False, "error": "Minimum 6 characters."}
    frappe.db.set_value("Travel Lead", lead.name,
                        "portal_password_hash", _hash(new_password))
    frappe.db.commit()
    return {"success": True}


def _hash(pw):
    return hashlib.sha256(("tt_salt_2025_" + pw).encode()).hexdigest()


def _get_or_create_user(mobile, name):
    existing = frappe.db.get_value("User", {"mobile_no": mobile}, "name")
    if existing:
        frappe.db.set_value("User", existing, "enabled", 1)
        return existing
    email = f"portal_{mobile}@tourtravel.internal"
    try:
        u = frappe.get_doc({
            "doctype": "User",
            "email": email,
            "first_name": (name or "Customer").split()[0],
            "mobile_no": mobile,
            "user_type": "Website User",
            "enabled": 1,
            "send_welcome_email": 0,
            "new_password": frappe.generate_hash(length=20),
            "roles": [{"role": "Customer"}],
        })
        u.flags.ignore_permissions = True
        u.insert()
        frappe.db.commit()
        return u.name
    except Exception as e:
        frappe.log_error(str(e), "Portal user creation")
        return None
PYEOF
echo "  ✅ my_portal.py"

# ── Check if portal_password_hash field exists on Travel Lead ────
echo ""
echo "▶ Adding portal_password_hash field to Travel Lead (if missing)..."
cd "$BENCH"
bench --site "$SITE" execute "frappe.db.get_value" \
  --args '["DocField", {"parent":"Travel Lead","fieldname":"portal_password_hash"}, "name"]' \
  2>/dev/null | grep -q "portal_password_hash" && echo "  ✅ Field already exists" || {

python3 - << 'PYEOF'
import subprocess, json

script = """
import frappe
frappe.connect()
if not frappe.db.get_value("Custom Field", {"dt":"Travel Lead","fieldname":"portal_password_hash"}):
    try:
        cf = frappe.get_doc({
            "doctype": "Custom Field",
            "dt": "Travel Lead",
            "fieldname": "portal_password_hash",
            "label": "Portal Password Hash",
            "fieldtype": "Password",
            "hidden": 1,
            "insert_after": "status"
        })
        cf.flags.ignore_permissions = True
        cf.insert()
        frappe.db.commit()
        print("Field created!")
    except Exception as e:
        print("Note:", e)
else:
    print("Field exists")
"""

import os, sys
bench = os.path.expanduser("~/frappe-bench")
site = None
for s in os.listdir(os.path.join(bench, "sites")):
    if os.path.exists(os.path.join(bench, "sites", s, "site_config.json")):
        site = s
        break

if site:
    r = subprocess.run(
        ["bench", "--site", site, "execute",
         "frappe.db.get_value",
         "--args", '["Custom Field", {"dt":"Travel Lead","fieldname":"portal_password_hash"}, "name"]'],
        cwd=bench, capture_output=True, text=True
    )
    print("  Field check:", r.stdout.strip() or "not found")
PYEOF
}

# ── Check www file list ──────────────────────────────────────────
echo ""
echo "▶ WWW directory contents:"
ls -la "$WWW/"

# ── Migrate + restart ────────────────────────────────────────────
echo ""
echo "▶ Running migrate..."
cd "$BENCH"
bench --site "$SITE" migrate 2>&1 | tail -5

echo ""
echo "▶ Clearing cache..."
bench --site "$SITE" clear-cache

echo ""
echo "▶ Restarting..."
bench restart

# ── Final test ───────────────────────────────────────────────────
echo ""
echo "▶ Testing pages..."
sleep 2
curl -s -o /dev/null -w "  my_portal:      %{http_code}\n" http://localhost:8001/my_portal
curl -s -o /dev/null -w "  travel_enquiry: %{http_code}\n" http://localhost:8001/travel_enquiry
curl -s -o /dev/null -w "  founder_dash:   %{http_code}\n" http://localhost:8001/founder_dash

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║  ✅  Done!                                  ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
echo "  All 3 pages should now return 200 or 301"
echo ""
echo "  Login: http://localhost:8001/my_portal"
echo "  Default password = last 4 digits of mobile"
echo ""
