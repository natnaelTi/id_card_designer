import frappe


def list_limit(n):
    return {"limit" if int(frappe.__version__.split(".")[0]) >= 16 else "limit_page_length": n}
