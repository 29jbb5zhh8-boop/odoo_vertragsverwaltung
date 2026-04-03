from odoo import api, fields, models


class ContractCostCenterBudget(models.Model):
    _name = "contract.cost.center.budget"
    _description = "Contract Cost Center Budget"
    _order = "code, department_id, id"

    name = fields.Char(string="Budgetname", required=True)
    code = fields.Char(string="Kostenstelle", required=True, index=True)
    department_id = fields.Many2one("hr.department", string="Abteilung")
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
    note = fields.Text(string="Notiz")

    @api.depends("code", "department_id", "monthly_budget", "annual_budget", "currency_id")
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
            if actual > budget:
                return "red"
            if actual >= (budget * 0.9):
                severity = "yellow"
        return severity

    def _search_budget_state(self, operator, value):
        if operator not in ("=", "!=") or value not in {"green", "yellow", "red"}:
            return [("id", "=", 0)]
        matching_ids = self.search([]).filtered(lambda rec: rec.budget_state == value).ids
        if operator == "=":
            return [("id", "in", matching_ids or [0])]
        return [("id", "not in", matching_ids or [0])]
