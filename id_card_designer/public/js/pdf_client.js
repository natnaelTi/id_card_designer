window.id_card_designer = {
  deliver_to_tab(tab, delivery) {
    // POST carries both the opaque capability and CSRF token. Neither appears in URLs/logs.
    const form = tab.document.createElement("form");
    form.method = "POST";
    form.action = window.location.origin + delivery.url;
    for (const [key, value] of Object.entries({
      token: delivery.token,
      csrf_token: frappe.csrf_token,
    })) {
      const input = tab.document.createElement("input");
      input.type = "hidden";
      input.name = key;
      input.value = value;
      form.append(input);
    }
    tab.document.body.append(form);
    tab.opener = null;
    form.submit();
  },
};
