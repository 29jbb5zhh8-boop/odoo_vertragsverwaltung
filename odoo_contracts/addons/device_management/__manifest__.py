{
    "name": "Geräteverwaltung",
    "version": "19.0.1.0.0",
    "category": "Tools",
    "summary": "Verwaltung von Kundengeräten",
    "description": "Verwaltung von Kundengeräten mit Dokumentenanhang.",
    "author": "Odoo Systemhaus",
    "license": "LGPL-3",
    "depends": ["base", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "views/device_views.xml",
        "reports/asset_label.xml",
    ],
    "application": True,
}
