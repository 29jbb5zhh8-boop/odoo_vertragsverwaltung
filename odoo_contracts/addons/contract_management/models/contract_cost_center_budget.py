from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ContractCostCenterBudget(models.Model):
    _name = "contract.cost.center.budget"
    _description = "Contract Cost Center Budget"
    _order = "code, department_id, id"

    name = fields.Char(string="Budgetname", required=True)
    code = fields.Char(string="Kostenstelle", required=True, index=True)
    department_id = fields.Many2one("hr.department", string="Abteilung")
    owner_user_id = fields.Many2one("res.users", string="Budgetverantwortlich")
    escalation_user_id = fields.Many2one("res.users", string="Eskalations-Empfaenger")
    currency_id = fields.Many2one(
        "res.currency",
        string="Waehrung",
        required=True,
        default=lambda self: self.env.company.currency_id.id,
    )
    monthly_budget = fields.Monetary(
        string="Monatsbudget",
        currency_field="currency_id",
    )
    annual_budget = fields.Monetary(
        string="Jahresbudget",
        currency_field="currency_id",
    )
    warning_threshold_pct = fields.Float(
        string="Warnschwelle (%)",
        default=90.0,
    )
    critical_threshold_pct = fields.Float(
        string="Kritische Schwelle (%)",
        default=100.0,
    )
    committed_monthly_value = fields.Monetary(
        string="Ist monatlich",
        currency_field="currency_id",
        compute="_compute_commitments",
    )
    committed_annual_value = fields.Monetary(
        string="Ist jaehrlich",
        currency_field="currency_id",
        compute="_compute_commitments",
    )
    monthly_variance = fields.Monetary(
        string="Monatsabweichung",
        currency_field="currency_id",
        compute="_compute_commitments",
    )
    annual_variance = fields.Monetary(
        string="Jahresabweichung",
        currency_field="currency_id",
        compute="_compute_commitments",
    )
    contract_count = fields.Integer(
        string="Aktive Vertraege",
        compute="_compute_commitments",
    )
    related_contract_ids = fields.Many2many(
        "contract.contract",
        string="Zugeordnete Vertraege",
        compute="_compute_commitments",
    )
    budget_state = fields.Selection(
        [
            ("green", "Im Budget"),
            ("yellow", "Beobachten"),
            ("red", "Ueber Budget"),
        ],
        string="Budgetstatus",
        compute="_compute_commitments",
        search="_search_budget_state",
    )
    active = fields.Boolean(default=True)
    last_notified_state = fields.Selection(
        [
            ("green", "Im Budget"),
            ("yellow", "Beobachten"),
            ("red", "Ueber Budget"),
        ],
        string="Zuletzt gemeldet",
        readonly=True,
        copy=False,
    )
    last_notified_at = fields.Datetime(string="Zuletzt gemeldet am", readonly=True, copy=False)
    note = fields.Text(string="Notiz")

    @api.depends(
        "code",
        "department_id",
        "monthly_budget",
        "annual_budget",
        "currency_id",
        "warning_threshold_pct",
        "critical_threshold_pct",
    )
    def _compute_commitments(self):
        contract_model = self.env["contract.contract"]
        today = fields.Date.context_today(self)
        for rec in self:
            if not rec.code or not rec.currency_id:
                rec.committed_monthly_value = 0.0
                rec.committed_annual_value = 0.0
                rec.monthly_variance = rec.monthly_budget or 0.0
                rec.annual_variance = rec.annual_budget or 0.0
                rec.contract_count = 0
                rec.related_contract_ids = [(6, 0, [])]
                rec.budget_state = "green"
                continue
            domain = [
                ("cost_center", "=ilike", rec.code),
                ("state", "in", ["active", "expiring"]),
                ("contract_kind", "!=", "customer"),
            ]
            if rec.department_id:
                domain.append(("department_id", "=", rec.department_id.id))
            contracts = contract_model.search(domain)
            monthly_total = 0.0
            annual_total = 0.0
            for contract in contracts:
                company_date = contract.start_date or today
                monthly_total += contract.currency_id._convert(
                    contract.normalized_monthly_value,
                    rec.currency_id,
                    self.env.company,
                    company_date,
                )
                annual_total += contract.currency_id._convert(
                    contract.normalized_annual_value,
                    rec.currency_id,
                    self.env.company,
                    company_date,
                )
            rec.committed_monthly_value = monthly_total
            rec.committed_annual_value = annual_total
            rec.monthly_variance = (rec.monthly_budget or 0.0) - monthly_total
            rec.annual_variance = (rec.annual_budget or 0.0) - annual_total
            rec.contract_count = len(contracts)
            rec.related_contract_ids = [(6, 0, contracts.ids)]
            rec.budget_state = rec._get_budget_state(monthly_total, annual_total)

    def _get_budget_state(self, monthly_total, annual_total):
        self.ensure_one()
        severity = "green"
        checks = [
            (self.monthly_budget, monthly_total),
            (self.annual_budget, annual_total),
        ]
        for budget, actual in checks:
            if not budget:
                continue
            critical_limit = budget * ((self.critical_threshold_pct or 100.0) / 100.0)
            warning_limit = budget * ((self.warning_threshold_pct or 90.0) / 100.0)
            if actual >= critical_limit:
                return "red"
            if actual >= warning_limit:
                severity = "yellow"
        return severity

    @api.constrains("warning_threshold_pct", "critical_threshold_pct")
    def _check_thresholds(self):
        for rec in self:
            if rec.warning_threshold_pct <= 0:
                raise ValidationError("Die Warnschwelle muss groesser als 0 sein.")
            if rec.critical_threshold_pct < rec.warning_threshold_pct:
                raise ValidationError("Die kritische Schwelle muss groesser oder gleich der Warnschwelle sein.")

    def action_open_related_contracts(self):
        self.ensure_one()
        domain = [
            ("id", "in", self.related_contract_ids.ids),
        ]
        return {
            "type": "ir.actions.act_window",
            "name": f"Vertraege zu {self.code}",
            "res_model": "contract.contract",
            "view_mode": "kanban,list,form,pivot,graph",
            "domain": domain,
            "context": {
                "search_default_group_cost_center": 1,
            },
        }

    def _search_budget_state(self, operator, value):
        if operator not in ("=", "!=") or value not in {"green", "yellow", "red"}:
            return [("id", "=", 0)]
        matching_ids = self.search([]).filtered(lambda rec: rec.budget_state == value).ids
        if operator == "=":
            return [("id", "in", matching_ids or [0])]
        return [("id", "not in", matching_ids or [0])]

    def _get_notification_user(self):
        self.ensure_one()
        return self.owner_user_id or self.escalation_user_id

    def _send_mail_template(self, xmlid):
        template = self.env.ref(xmlid, raise_if_not_found=False)
        if not template:
            return
        for rec in self:
            template.send_mail(rec.id, force_send=False)

    def _create_budget_activity(self, summary, note, user):
        activity_type = self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)
        if not activity_type or not user:
            return
        model_id = self.env["ir.model"]._get_id("contract.cost.center.budget")
        for rec in self:
            existing = self.env["mail.activity"].sudo().search(
                [
                    ("res_model", "=", "contract.cost.center.budget"),
                    ("res_id", "=", rec.id),
                    ("summary", "=", summary),
                    ("user_id", "=", user.id),
                ],
                limit=1,
            )
            if existing:
                continue
            self.env["mail.activity"].sudo().create(
                {
                    "activity_type_id": activity_type.id,
                    "summary": summary,
                    "note": note,
                    "date_deadline": fields.Date.context_today(rec),
                    "res_model_id": model_id,
                    "res_id": rec.id,
                    "user_id": user.id,
                }
            )

    def _cron_budget_escalation(self):
        budgets = self.search([("active", "=", True)])
        for budget in budgets:
            if budget.budget_state not in {"yellow", "red"}:
                continue
            if budget.last_notified_state == budget.budget_state:
                continue
            target_user = budget._get_notification_user()
            if budget.budget_state == "red":
                if budget.escalation_user_id:
                    target_user = budget.escalation_user_id
                budget._send_mail_template("contract_management.mail_template_budget_red")
                summary = "Budget: Kostenstelle ueber Budget"
                note = (
                    f"Kostenstelle {budget.code} liegt ueber Budget. "
                    f"Monatlich: {budget.committed_monthly_value} / {budget.monthly_budget or 0.0}. "
                    f"Jaehrlich: {budget.committed_annual_value} / {budget.annual_budget or 0.0}."
                )
            else:
                budget._send_mail_template("contract_management.mail_template_budget_yellow")
                summary = "Budget: Kostenstelle beobachten"
                note = (
                    f"Kostenstelle {budget.code} hat die Warnschwelle erreicht. "
                    f"Monatlich: {budget.committed_monthly_value} / {budget.monthly_budget or 0.0}. "
                    f"Jaehrlich: {budget.committed_annual_value} / {budget.annual_budget or 0.0}."
                )
            if target_user:
                budget._create_budget_activity(summary=summary, note=note, user=target_user)
            budget.write(
                {
                    "last_notified_state": budget.budget_state,
                    "last_notified_at": fields.Datetime.now(),
                }
            )
