# Travel Tour Management System

A comprehensive ERPNext v15+ custom application for travel agencies, tour operators, and visa consultants. This app provides a unified platform to manage tour packages, bookings, supplier allotments, CRM leads, and a full-scale visa management operation.

## 🚀 Key Modules

### 1. Package & Itinerary Management
- Create beautiful tour packages with slab-based price variants.
- Build detailed daily itineraries with meal plans and activities.
- Manage destinations as master data.

### 2. Booking & Reservation System
- Professional Booking engine with Pax (passenger) management.
- Automated calculation of totals, taxes (GST), and TCS (Tax Collected at Source) for international travel.
- Integration for addons and discounts.

### 3. Visa Management (Pro)
- End-to-end visa lifecycle tracking (Pending -> Submitted -> Approved -> Delivered).
- Country-specific document checklists and processing time tracking.
- Automated visa billing and integration with Sales Invoices.
- Embassy appointment scheduling and delivery logs.

### 4. Supplier & Operations
- Manage hotel allotments and room inventory.
- Track supplier contracts and costs.
- Operational "Run Sheets" and Guide Allocation with conflict detection.

### 5. CRM & Finance
- Lead management with round-robin consultant assignment.
- Dedicated "Travel Tour" Workspace for real-time visibility.
- Singleton settings for global configuration (API keys, commission rates).

## 🛠 Tech Stack
- **Framework**: Frappe v15+
- **Application**: ERPNext v15+
- **Database**: MariaDB
- **UI**: Frappe Desk (Custom Workspace)

## 📦 Installation

To install this app on your Frappe bench:

```bash
# Get the app
bench get-app https://github.com/balaji-001-gif/tour_travels.git

# Install on your site
bench --site [your-site-name] install-app travel_tour

# Run migrations
bench migrate
```

## ⚙️ Configuration
1. Navigate to **Travel Tour Settings**.
2. Configure your Operations Email and site URL.
3. (Optional) Provide Razorpay API keys for payment gateway integration.
4. Set up **Visa Country Config** for each destination you handle.

## 📝 License
This project is licensed under the MIT License.
