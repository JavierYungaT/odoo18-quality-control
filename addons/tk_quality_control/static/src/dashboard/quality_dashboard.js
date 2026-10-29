import { Component, onWillStart, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";

export class QualityDashboard extends Component {
    static template = "tk_quality_control.QualityDashboard";
    static props = { ...standardActionServiceProps };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ data: null, loading: true });
        onWillStart(() => this.load());
    }

    async load() {
        this.state.loading = true;
        this.state.data = await this.orm.call("tk.quality.check", "get_dashboard_data", []);
        this.state.loading = false;
    }

    get kpis() {
        const data = this.state.data;
        return [
            {
                key: "pending",
                label: _t("Checks to do"),
                value: data.pending,
                hint: _t("Waiting for an inspector"),
                tone: data.pending ? "warning" : "neutral",
                open: () => this.openChecks({ search_default_pending: 1 }),
            },
            {
                key: "pass_rate",
                label: _t("Pass rate (30 days)"),
                value: data.pass_rate_30d === null ? "—" : `${data.pass_rate_30d} %`,
                hint: _t("%(done)s checks, %(failed)s failed", {
                    done: data.done_30d,
                    failed: data.failed_30d,
                }),
                tone: "neutral",
                open: () => this.openChecks({ search_default_done: 1 }),
            },
            {
                key: "open_alerts",
                label: _t("Open alerts"),
                value: data.open_alerts,
                hint: _t("Non-conformities not closed"),
                tone: data.open_alerts ? "danger" : "neutral",
                open: () => this.openAlerts({ search_default_open: 1 }),
            },
            {
                key: "open_cost",
                label: _t("Cost of open alerts"),
                value: data.open_cost,
                hint: _t("Affected quantity at product cost"),
                tone: "neutral",
                open: () => this.openAlerts({ search_default_open: 1 }),
            },
        ];
    }

    get maxStageCount() {
        return Math.max(1, ...this.state.data.stages.map((stage) => stage.count));
    }

    scoreClass(score) {
        if (score >= 90) {
            return "text-bg-success";
        }
        return score >= 75 ? "text-bg-warning" : "text-bg-danger";
    }

    openChecks(context) {
        this.action.doAction("tk_quality_control.action_tk_quality_check", {
            additionalContext: context,
        });
    }

    openAlerts(context) {
        this.action.doAction("tk_quality_control.action_tk_quality_alert", {
            additionalContext: context,
        });
    }

    openStage(stage) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: stage.name,
            res_model: "tk.quality.alert",
            views: [
                [false, "list"],
                [false, "form"],
            ],
            domain: [["stage_id", "=", stage.id]],
        });
    }

    openSupplier(supplier) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "res.partner",
            res_id: supplier.id,
            views: [[false, "form"]],
        });
    }
}

registry.category("actions").add("tk_quality_control.dashboard", QualityDashboard);
