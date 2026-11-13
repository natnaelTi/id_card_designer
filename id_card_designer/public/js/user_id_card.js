frappe.ui.form.on("User", {
  async refresh(frm) {
    if (frm.is_new()) return;
    const { message: caps } = await frappe.call(
      "id_card_designer.api.capabilities",
      { user: frm.doc.name }
    );
    if (!caps.print || frm.is_new()) return;
    frm.add_custom_button(__("Print ID Card"), async () => {
      const { message: templates } = await frappe.call(
        "id_card_designer.api.list_usable_templates"
      );
      if (!templates.length)
        return frappe.msgprint(
          __(
            "No active published templates are available. Ask an ID Card Manager to publish one."
          )
        );
      const d = new frappe.ui.Dialog({
        title: __("Print ID Card"),
        fields: [
          { fieldname: "gallery", fieldtype: "HTML" },
          {
            fieldname: "template",
            label: __("Template"),
            fieldtype: "Select",
            reqd: 1,
            options: templates.map((t) => ({ label: t.title, value: t.name })),
            default: (templates.find((t) => t.is_default) || templates[0]).name,
          },
        ],
        primary_action_label: __("Print"),
        primary_action: async (values) => {
          const tab = window.open("about:blank", "_blank");
          if (!tab)
            return frappe.msgprint(
              __("Allow popups for this site and click Print again.")
            );
          tab.opener = null;
          try {
            const { message: url } = await frappe.call(
              "id_card_designer.api.prepare_pdf",
              { name: values.template, user: frm.doc.name }
            );
            id_card_designer.deliver_to_tab(tab, url);
            d.hide();
          } catch (e) {
            tab.close();
          }
        },
      });
      d.fields_dict.gallery.$wrapper.html(
        templates
          .map(
            (t) =>
              `<div class="my-2"><img alt="Institutional sample thumbnail" src="${frappe.utils.escape_html(
                t.thumbnail
              )}" width="110"> <strong>${frappe.utils.escape_html(
                t.title
              )}</strong> · ${t.width_mm} × ${t.height_mm} mm ${
                t.is_default ? "· Default" : ""
              }</div>`
          )
          .join("")
      );
      d.set_secondary_action_label(__("Cancel"));
      d.set_secondary_action(() => d.hide());
      d.show();
    });
  },
});
