frappe.ui.form.on('Booking', {
    refresh: function(frm) {
    },
    tour_package: function(frm) {
        if (frm.doc.tour_package && frm.doc.total_pax) {
            frm.trigger('calculate_totals');
        }
    },
    total_pax: function(frm) {
        if (frm.doc.tour_package && frm.doc.total_pax) {
            frm.trigger('calculate_totals');
        }
    },
    calculate_totals: function(frm) {
        frappe.call({
            method: 'calculate_totals',
            doc: frm.doc,
            callback: function(r) {
                frm.refresh_fields(['base_amount', 'gst_amount', 'tcs_amount', 'grand_total']);
            }
        });
    }
});
