{
    "name": "Quality Control",
    "summary": "Quality points, inspections and non-conformities for receipts, "
    "deliveries and manufacturing orders",
    "description": """
Quality control for Odoo Community: control points per operation type,
automatic inspections that block validation, non-conformity tracking with
cost, supplier quality score, QWeb reports and an OWL dashboard.
""",
    "version": "18.0.1.1.0",
    "category": "Manufacturing/Quality",
    "author": "Javier Yunga",
    "website": "https://github.com/JavierYungaT/odoo18-quality-control",
    "license": "LGPL-3",
    "depends": ["hr", "mail", "mrp", "purchase_stock", "sale_stock"],
    "data": [
        "security/tk_quality_security.xml",
        "security/ir.model.access.csv",
        "data/ir_sequence_data.xml",
        "data/tk_quality_alert_stage_data.xml",
        "data/ir_cron_data.xml",
        "data/ir_actions_server_data.xml",
        "report/tk_quality_reports.xml",
        "report/report_quality_certificate.xml",
        "report/report_quality_alert.xml",
        "report/report_supplier_quality.xml",
        "views/tk_quality_point_views.xml",
        "views/tk_quality_check_views.xml",
        "views/tk_quality_alert_views.xml",
        "views/tk_quality_alert_stage_views.xml",
        "views/tk_quality_report_views.xml",
        "views/stock_picking_views.xml",
        "views/mrp_production_views.xml",
        "views/purchase_order_views.xml",
        "views/sale_order_views.xml",
        "views/res_partner_views.xml",
        "views/res_config_settings_views.xml",
        "views/tk_quality_menus.xml",
    ],
    "demo": ["demo/tk_quality_demo.xml"],
    "assets": {
        "web.assets_backend": [
            "tk_quality_control/static/src/**/*",
        ],
    },
    "application": True,
    "installable": True,
}
