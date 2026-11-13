app_name = "id_card_designer"
app_title = "ID Card Designer"
app_publisher = "Institutional Tools"
app_description = "Institutional ID cards — not an official government credential issuer"
app_email = "admin@example.invalid"
app_license = "MIT"
doctype_js = {"User": "public/js/user_id_card.js", "ID Card Template": "public/js/template.js"}
after_install = "id_card_designer.install.seed"
after_migrate = "id_card_designer.install.seed"
after_request = ["id_card_designer.api.secure_pdf_headers"]

has_permission = {
    "ID Card Template": "id_card_designer.id_card_designer.doctype.id_card_template.id_card_template.has_permission",
    "ID Card Profile": "id_card_designer.id_card_designer.doctype.id_card_profile.id_card_profile.has_permission",
}
permission_query_conditions = {
    "ID Card Profile": "id_card_designer.id_card_designer.doctype.id_card_profile.id_card_profile.get_permission_query_conditions"
}
app_include_js = [
    "/assets/id_card_designer/js/pdf_client.js",
    "/assets/id_card_designer/js/autosave.js",
    "/assets/id_card_designer/js/scene.js",
]
scheduler_events = {"daily": ["id_card_designer.maintenance.prune_audit"]}
before_tests = "id_card_designer.testing.bootstrap"
