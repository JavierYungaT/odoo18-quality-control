from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import Form, TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestQualityFlow(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Isolate the tests from control points loaded as demo data.
        cls.env["tk.quality.point"].search([]).active = False
        cls.picking_type_in = cls.env.ref("stock.picking_type_in")
        cls.stock_location = cls.env.ref("stock.stock_location_stock")
        cls.supplier_location = cls.env.ref("stock.stock_location_suppliers")
        cls.category = cls.env["product.category"].create({"name": "Test Wood"})
        cls.board = cls.env["product.product"].create({
            "name": "Test Board",
            "is_storable": True,
            "categ_id": cls.category.id,
            "standard_price": 5.0,
        })
        cls.screw = cls.env["product.product"].create({"name": "Test Screw", "is_storable": True})
        cls.vendor = cls.env["res.partner"].create({"name": "Test Vendor"})
        cls.visual_point = cls.env["tk.quality.point"].create({
            "name": "Visual",
            "picking_type_ids": [(6, 0, cls.picking_type_in.ids)],
            "test_type": "pass_fail",
        })
        cls.moisture_point = cls.env["tk.quality.point"].create({
            "name": "Moisture",
            "picking_type_ids": [(6, 0, cls.picking_type_in.ids)],
            "product_category_ids": [(6, 0, cls.category.ids)],
            "test_type": "measure",
            "norm": 12,
            "tolerance_min": 8,
            "tolerance_max": 14,
        })

    def _create_receipt(self, products):
        picking = self.env["stock.picking"].create({
            "partner_id": self.vendor.id,
            "picking_type_id": self.picking_type_in.id,
            "location_id": self.supplier_location.id,
            "location_dest_id": self.stock_location.id,
            "move_ids": [
                (0, 0, {
                    "name": product.name,
                    "product_id": product.id,
                    "product_uom_qty": 10,
                    "product_uom": product.uom_id.id,
                    "location_id": self.supplier_location.id,
                    "location_dest_id": self.stock_location.id,
                })
                for product in products
            ],
        })
        picking.action_confirm()
        return picking

    def _set_quantities_done(self, picking):
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty
        picking.move_ids.picked = True

    def test_checks_generated_on_confirm(self):
        picking = self._create_receipt(self.board | self.screw)
        checks = picking.tk_quality_check_ids
        # Visual applies to both products, moisture only to the wood category.
        self.assertEqual(len(checks), 3)
        self.assertEqual(set(checks.mapped("state")), {"pending"})
        self.assertEqual(checks.supplier_id, self.vendor)
        self.assertEqual(picking.tk_quality_state, "pending")

    def test_checks_not_duplicated(self):
        picking = self._create_receipt(self.board)
        picking._tk_generate_quality_checks()
        self.assertEqual(len(picking.tk_quality_check_ids), 2)

    def test_purchase_receipt_generates_checks(self):
        order = self.env["purchase.order"].create({
            "partner_id": self.vendor.id,
            "order_line": [(0, 0, {"product_id": self.board.id, "product_qty": 5, "price_unit": 5})],
        })
        order.button_confirm()
        self.assertEqual(len(order.picking_ids.tk_quality_check_ids), 2)

    def test_validation_blocked_while_pending(self):
        picking = self._create_receipt(self.screw)
        self._set_quantities_done(picking)
        with self.assertRaises(UserError):
            picking.button_validate()

    def test_failed_check_requires_alert(self):
        picking = self._create_receipt(self.screw)
        self._set_quantities_done(picking)
        check = picking.tk_quality_check_ids
        check.action_fail()
        with self.assertRaises(UserError):
            picking.button_validate()

        self.env["tk.quality.alert"].create({"title": "Damaged screws", "check_id": check.id})
        picking.button_validate()
        self.assertEqual(picking.state, "done")
        self.assertEqual(picking.tk_quality_state, "fail")

    def test_measure_within_tolerance(self):
        picking = self._create_receipt(self.board)
        moisture = picking.tk_quality_check_ids.filtered(lambda c: c.point_id == self.moisture_point)
        moisture.measure = 11
        moisture.action_validate_measure()
        self.assertEqual(moisture.state, "pass")

    def test_measure_out_of_tolerance(self):
        picking = self._create_receipt(self.board)
        moisture = picking.tk_quality_check_ids.filtered(lambda c: c.point_id == self.moisture_point)
        moisture.measure = 17
        moisture.action_validate_measure()
        self.assertEqual(moisture.state, "fail")
        # The constraint forbids forcing a result that contradicts the measure.
        with self.assertRaises(ValidationError):
            moisture.state = "pass"

    def test_measure_check_cannot_be_passed_directly(self):
        picking = self._create_receipt(self.board)
        moisture = picking.tk_quality_check_ids.filtered(lambda c: c.point_id == self.moisture_point)
        with self.assertRaises(UserError):
            moisture.action_pass()

    def test_point_tolerance_constraint(self):
        with self.assertRaises(ValidationError):
            self.env["tk.quality.point"].create({
                "name": "Wrong",
                "picking_type_ids": [(6, 0, self.picking_type_in.ids)],
                "test_type": "measure",
                "norm": 5,
                "tolerance_min": 10,
                "tolerance_max": 1,
            })

    def test_supplier_score(self):
        picking = self._create_receipt(self.board | self.screw)
        checks = picking.tk_quality_check_ids.filtered(lambda c: c.test_type == "pass_fail")
        checks[0].action_pass()
        checks[1].action_fail()
        moisture = picking.tk_quality_check_ids - checks
        moisture.measure = 10
        moisture.action_validate_measure()
        self.assertEqual(self.vendor.supplier_quality_check_count, 3)
        self.assertAlmostEqual(self.vendor.supplier_quality_score, 66.7, places=1)

    def test_purchase_warning_below_min_score(self):
        self.env["ir.config_parameter"].sudo().set_param("tk_quality_control.supplier_min_score", 80)
        picking = self._create_receipt(self.screw)
        picking.tk_quality_check_ids.action_fail()
        order = self.env["purchase.order"].new({"partner_id": self.vendor.id})
        self.assertTrue(order.tk_show_quality_warning)

    def test_alert_cost_and_closing_rules(self):
        alert = self.env["tk.quality.alert"].create({
            "title": "Cracked boards",
            "product_id": self.board.id,
            "quantity": 4,
        })
        self.assertTrue(alert.name.startswith("QA/"))
        self.assertEqual(alert.cost, 20.0)

        closed_stage = self.env.ref("tk_quality_control.stage_closed")
        with self.assertRaises(ValidationError):
            alert.stage_id = closed_stage

        alert.write({
            "root_cause": "Humidity in the warehouse",
            "corrective_action": "<p>Dehumidifier installed</p>",
            "stage_id": closed_stage.id,
        })
        self.assertTrue(alert.is_closed)
        self.assertTrue(alert.date_closed)

    def test_customer_complaint_from_sale_order(self):
        order = self.env["sale.order"].create({
            "partner_id": self.vendor.id,
            "order_line": [(0, 0, {"product_id": self.board.id, "product_uom_qty": 1})],
        })
        order.action_confirm()
        action = order.action_tk_report_quality_issue()
        form = Form(self.env["tk.quality.alert"].with_context(action["context"]))
        alert = form.save()
        self.assertEqual(alert.origin, "customer")
        self.assertEqual(alert.product_id, self.board)
        self.assertEqual(order.tk_quality_alert_count, 1)

    def test_overdue_cron_schedules_activity(self):
        employee = self.env["hr.employee"].create({"name": "Inspector", "user_id": self.env.user.id})
        alert = self.env["tk.quality.alert"].create({
            "title": "Late",
            "product_id": self.board.id,
            "employee_id": employee.id,
            "date_deadline": "2020-01-01",
        })
        self.env["tk.quality.alert"]._cron_schedule_overdue_activities()
        self.env["tk.quality.alert"]._cron_schedule_overdue_activities()
        self.assertEqual(len(alert.activity_ids), 1)

    def test_analysis_view_and_dashboard(self):
        picking = self._create_receipt(self.screw)
        picking.tk_quality_check_ids.action_pass()
        self.env.flush_all()
        rows = self.env["tk.quality.report"].search([("supplier_id", "=", self.vendor.id)])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows.pass_rate, 100.0)

        data = self.env["tk.quality.check"].get_dashboard_data()
        for key in ("pending", "pass_rate_30d", "open_alerts", "open_cost", "stages", "suppliers"):
            self.assertIn(key, data)

    def test_reports_render(self):
        picking = self._create_receipt(self.screw)
        picking.tk_quality_check_ids.action_pass()
        Report = self.env["ir.actions.report"]
        html, _ = Report._render_qweb_html(
            "tk_quality_control.action_report_quality_certificate", picking.ids
        )
        self.assertIn(picking.name, html.decode())
        html, _ = Report._render_qweb_html(
            "tk_quality_control.action_report_supplier_quality", self.vendor.ids
        )
        self.assertIn("Test Vendor", html.decode())
        alert = self.env["tk.quality.alert"].create({
            "title": "Bent screws",
            "product_id": self.screw.id,
            "partner_id": self.vendor.id,
        })
        html, _ = Report._render_qweb_html(
            "tk_quality_control.action_report_quality_alert", alert.ids
        )
        self.assertIn("Bent screws", html.decode())

    def test_backorder_gets_checks(self):
        picking = self._create_receipt(self.screw)
        picking.tk_quality_check_ids.action_pass()
        picking.move_ids.quantity = 4
        picking.move_ids.picked = True
        picking.with_context(cancel_backorder=False)._action_done()
        backorder = picking.backorder_ids
        self.assertTrue(backorder)
        self.assertEqual(backorder.tk_quality_state, "pending")
        self._set_quantities_done(backorder)
        with self.assertRaises(UserError):
            backorder.button_validate()

    def test_inspector_is_who_records_the_result(self):
        inspector_user = self.env["res.users"].create({
            "name": "Inspector User",
            "login": "tk_inspector",
            "groups_id": [(6, 0, self.env.ref("tk_quality_control.group_quality_user").ids)],
        })
        inspector = self.env["hr.employee"].create({"name": "Inspector", "user_id": inspector_user.id})
        self.env["hr.employee"].create({"name": "Buyer", "user_id": self.env.user.id})
        picking = self._create_receipt(self.screw)
        check = picking.tk_quality_check_ids
        self.assertFalse(check.inspector_id)
        check.with_user(inspector_user).action_pass()
        self.assertEqual(check.inspector_id, inspector)

    def test_reset_restricted(self):
        user = self.env["res.users"].create({
            "name": "Quality User",
            "login": "tk_quality_user",
            "groups_id": [(6, 0, self.env.ref("tk_quality_control.group_quality_user").ids)],
        })
        picking = self._create_receipt(self.screw)
        check = picking.tk_quality_check_ids
        check.action_pass()
        with self.assertRaises(AccessError):
            check.with_user(user).action_reset()

        self._set_quantities_done(picking)
        picking.button_validate()
        with self.assertRaises(UserError):
            check.action_reset()

    def test_check_keeps_tolerances_of_its_inspection(self):
        picking = self._create_receipt(self.board)
        moisture = picking.tk_quality_check_ids.filtered(lambda c: c.point_id == self.moisture_point)
        moisture.measure = 13
        moisture.action_validate_measure()
        self.moisture_point.write({"norm": 10, "tolerance_min": 9, "tolerance_max": 11})
        self.assertEqual(moisture.tolerance_max, 14)
        self.assertTrue(moisture.is_within_tolerance)
        self.assertEqual(moisture.state, "pass")

    def test_production_blocked_until_inspected(self):
        manu_type = self.env.ref("stock.warehouse0").manu_type_id
        self.env["tk.quality.point"].create({
            "name": "Final inspection",
            "picking_type_ids": [(6, 0, manu_type.ids)],
            "test_type": "pass_fail",
        })
        form = Form(self.env["mrp.production"])
        form.product_id = self.board
        form.picking_type_id = manu_type
        form.product_qty = 1
        production = form.save()
        production.action_confirm()
        self.assertEqual(production.tk_quality_state, "pending")
        production.qty_producing = 1
        with self.assertRaises(UserError):
            production.button_mark_done()
        production.tk_quality_check_ids.action_pass()
        production.button_mark_done()
        self.assertEqual(production.state, "done")
