import frappe
from frappe.utils import today, add_days, getdate
import random

def create_demo_data():
    """
    Populates extensive demo data (5-10 records per DocType) for the Travel Tour application.
    """
    frappe.flags.in_test = True

    try:
        # 0. Ensure base items for allotments
        if not frappe.db.exists("Item", "Standard Double"):
            frappe.get_doc({
                "doctype": "Item",
                "item_code": "Standard Double",
                "item_name": "Standard Double Room",
                "item_group": "All Item Groups",
                "is_stock_item": 0
            }).insert(ignore_permissions=True)

        # ────────── 1. DESTINATIONS (10) ──────────
        print("Creating 10 Destinations...")
        destinations = [
            ("Dubai", "United Arab Emirates"), ("Maldives", "Maldives"), ("Switzerland", "Switzerland"),
            ("Thailand", "Thailand"), ("Singapore", "Singapore"), ("Malaysia", "Malaysia"),
            ("Bali", "Indonesia"), ("Paris", "France"), ("London", "United Kingdom"), ("New York", "United States")
        ]
        
        for dest, country in destinations:
            if not frappe.db.exists("Destination", dest):
                frappe.get_doc({
                    "doctype": "Destination", "destination_name": dest, "country": country, "status": "Active"
                }).insert(ignore_permissions=True)

        # ────────── 2. TOUR PACKAGES (10) ──────────
        print("Creating 10 Tour Packages...")
        packages = []
        for i, (dest, country) in enumerate(destinations):
            pkg_name = f"Signature {dest} Premium Tour"
            if not frappe.db.exists("Tour Package", pkg_name):
                doc = frappe.get_doc({
                    "doctype": "Tour Package",
                    "package_name": pkg_name,
                    "destination": dest,
                    "duration_days": random.randint(4, 7),
                    "duration_nights": random.randint(3, 6),
                    "status": "Active",
                    "tour_type": "International",
                    "description": "Premium Hotel, Daily Breakfast, Guided Tours, Transfers",
                    "itinerary": [
                        {"day_number": 1, "title": "Arrival", "description": f"Welcome to {dest}. Airport transfer to luxury hotel."},
                        {"day_number": 2, "title": "City Highlights", "description": f"Exploring the premium zones of {dest}."},
                        {"day_number": 3, "title": "Leisure & Shopping", "description": "Free time for leisure activities."}
                    ],
                    "pricing_table": [
                        {"min_pax": 1, "max_pax": 2, "per_person_price": random.randint(1000, 2000)},
                        {"min_pax": 3, "max_pax": 10, "per_person_price": random.randint(800, 1500)}
                    ]
                }).insert(ignore_permissions=True)
                packages.append(doc)

        # ────────── 3. TRAVEL LEADS (10) ──────────
        print("Creating 10 Travel Leads...")
        lead_names = ["Alice Smith", "Bob Johnson", "Charlie Davis", "Diana Prince", "Eve Adams", 
                      "Frank Castle", "Grace Hopper", "Hank Pym", "Ivy Fern", "Jack Sparrow"]
        
        leads = []
        for i, name in enumerate(lead_names):
            if not frappe.db.exists("Travel Lead", {"email_id": f"client{i}@example.com"}):
                doc = frappe.get_doc({
                    "doctype": "Travel Lead",
                    "customer_name": name,
                    "email_id": f"client{i}@example.com",
                    "mobile_no": f"+100000000{i}",
                    "suggested_package": f"Signature {destinations[i][0]} Premium Tour",
                    "pax_count": random.randint(1, 4),
                    "status": random.choice(["Open", "Interested", "converted", "Lost"]),
                    "source": random.choice(["Website", "Referral", "Social Media"])
                }).insert(ignore_permissions=True)
                leads.append(doc)

        # ────────── 4. SUPPLIER CONTRACTS (5) ──────────
        print("Creating 5 Supplier Contracts...")
        suppliers = ["Marriott International", "Hilton Hotels", "Emirates Transport", "Skyline Tours", "Oceanic Voyages"]
        
        for i, supp in enumerate(suppliers):
            # Ensure the core Supplier exists first
            if not frappe.db.exists("Supplier", supp):
                frappe.get_doc({
                    "doctype": "Supplier",
                    "supplier_name": supp,
                    "supplier_group": "All Supplier Groups"
                }).insert(ignore_permissions=True)

            if not frappe.db.exists("Supplier Contract", {"supplier": supp}):
                frappe.get_doc({
                    "doctype": "Supplier Contract",
                    "supplier": supp,
                    "supplier_name": supp,
                    "cost_per_pax": random.randint(100, 500),
                    "contract_start_date": today(),
                    "contract_end_date": add_days(today(), 365)
                }).insert(ignore_permissions=True)

        # ────────── 5. VISA CONFIGS (5) ──────────
        print("Creating 5 Visa Country Configs...")
        for dest, country in destinations[:5]:
            if not frappe.db.exists("Visa Country Config", {"country": country, "visa_type": "Tourist"}):
                frappe.get_doc({
                    "doctype": "Visa Country Config",
                    "country": country,
                    "visa_type": "Tourist",
                    "processing_time_days": 5,
                    "base_fee": random.randint(50, 150),
                    "required_documents": [
                        {"document_name": "Passport Copy - Front & Back", "is_mandatory": 1},
                        {"document_name": "Photograph (White Background)", "is_mandatory": 1},
                        {"document_name": "6 Months Bank Statement", "is_mandatory": 0}
                    ]
                }).insert(ignore_permissions=True)

        # ────────── 6. BOOKINGS (5) ──────────
        print("Creating 5 Confirmed Bookings...")
        for i in range(5):
            lead = leads[i]
            
            # Ensure Customer exists
            if not frappe.db.exists("Customer", lead.customer_name):
                frappe.get_doc({
                    "doctype": "Customer",
                    "customer_name": lead.customer_name,
                    "customer_group": "All Customer Groups",
                    "customer_type": "Individual",
                    "territory": "All Territories"
                }).insert(ignore_permissions=True)

            if not frappe.db.exists("Booking", {"travel_lead": lead.name}):
                bk = frappe.get_doc({
                    "doctype": "Booking",
                    "customer": lead.customer_name,
                    "travel_lead": lead.name,
                    "tour_package": lead.suggested_package,
                    "departure_date": add_days(today(), random.randint(10, 30)),
                    "total_pax": lead.pax_count,
                    "booking_status": "Confirmed",
                    "pax_details": [
                        {"pax_name": lead.customer_name, "pax_age": 30, "passport_number": f"P{1000+i}X"},
                        {"pax_name": f"{lead.customer_name} Partner", "pax_age": 28, "passport_number": f"P{2000+i}Y"}
                    ] if lead.pax_count > 1 else [
                        {"pax_name": lead.customer_name, "pax_age": 30, "passport_number": f"P{1000+i}X"}
                    ]
                }).insert(ignore_permissions=True)
                
                # Create related operational docs
                print(f"Creating Operational Docs for Booking: {bk.name}")
                
                # 7. VISA APPLICATION
                print(f"Creating Visa App for: {lead.customer_name}")
                frappe.get_doc({
                    "doctype": "Visa Application",
                    "booking": bk.name,
                    "applicant_name": lead.customer_name,
                    "destination_country": destinations[i][1],
                    "status": "Pending Documents",
                    "visa_type": "Tourist",
                    "departure_date": bk.departure_date,
                    "submission_deadline": add_days(today(), 5)
                }).insert(ignore_permissions=True)
                
                # 8. HOTEL ALLOTMENT
                print(f"Creating Hotel Allotment for: {suppliers[i % 2]}")
                frappe.get_doc({
                    "doctype": "Hotel Allotment",
                    "supplier": suppliers[i % 2],
                    "from_date": bk.departure_date,
                    "to_date": add_days(bk.departure_date, 3),
                    "rooms": [
                        {"room_type": "Standard Double", "quantity": 1}
                    ]
                }).insert(ignore_permissions=True)
                
                # 9. TRIP RUN SHEET
                print(f"Creating Run Sheet for: {bk.name}")
                frappe.get_doc({
                    "doctype": "Trip Run Sheet",
                    "booking": bk.name,
                    "customer": lead.customer_name,
                    "departure_date": bk.departure_date,
                    "total_pax": lead.pax_count,
                    "activities": [
                        {"activity_time": "09:00:00", "activity_name": "Airport Pick-up", "description": "Meet and greet at arrivals."}
                    ]
                }).insert(ignore_permissions=True)

        frappe.db.commit()
        print("\n✅ Success! 5 to 10 records for EVERY major DocType have been generated!")
        
    except Exception as e:
        print(f"\n❌ Error populating demo data: {e}")
        frappe.db.rollback()


def cleanup_workspace():
    """
    Force deletes the 'Travel Tour' workspace from the database to clear UI crashes.
    """
    print("🧹 Cleaning up broken workspace data...")
    if frappe.db.exists("Workspace", "Travel Tour"):
        frappe.delete_doc("Workspace", "Travel Tour", ignore_permissions=True, force=True)
        frappe.db.commit()
        print("✅ 'Travel Tour' workspace deleted from database.")
    else:
        print("ℹ️ No 'Travel Tour' workspace found in database.")
    
    frappe.clear_cache()
    print("✨ Cache cleared. Sidebar should restore on refresh.")

