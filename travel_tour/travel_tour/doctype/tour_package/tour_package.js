frappe.ui.form.on('Tour Package', {
	refresh: function(frm) {
	},
    duration_nights: function(frm) {
        if (frm.doc.duration_nights) {
            frm.set_value('duration_days', frm.doc.duration_nights + 1);
        }
    }
});
