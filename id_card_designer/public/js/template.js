frappe.ui.form.on("ID Card Template", {
  refresh(frm) {
    if (!frm.is_new())
      frm.add_custom_button(__("Open Designer"), () =>
        frappe.set_route("id-card-builder", frm.doc.name)
      );
  },
});
