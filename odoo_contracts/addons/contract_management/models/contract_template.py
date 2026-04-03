from odoo import fields, models


class ContractTemplate(models.Model):
    _name = "contract.template"
    _description = "Contract Template"
    _order = "name"

    name = fields.Char(string="Vorlagenname", required=True, translate=True)
    active = fields.Boolean(default=True)
    contract_kind = fields.Selection(
        [
            ("supplier", "Lieferant"),
            ("customer", "Kunde"),
            ("rent", "Miete"),
            ("lease", "Leasing"),
            ("maintenance", "Wartung"),
            ("service", "Dienstleistung"),
            ("license", "Lizenz"),
            ("insurance", "Versicherung"),
            ("other", "Sonstiges"),
        ],
        string="Vertragsart",
        required=True,
        default="supplier",
    )
    type_id = fields.Many2one("contract.type", string="Vertragstyp")
    category_id = fields.Many2one("contract.category", string="Vertragskategorie")
    department_id = fields.Many2one("hr.department", string="Abteilung")
    responsible_user_id = fields.Many2one("res.users", string="Verantwortlich")
    approval_user_id = fields.Many2one("res.users", string="Freigeber")
    manager_approval_user_id = fields.Many2one("res.users", string="Manager-Freigeber")
    currency_id = fields.Many2one(
        "res.currency",
        string="Waehrung",
        required=True,
        default=lambda self: self.env.company.currency_id.id,
    )
    contract_value = fields.Monetary(
        string="Standard-Vertragswert",
        currency_field="currency_id",
    )
    payment_interval = fields.Selection(
        [
            ("monthly", "Monatlich"),
            ("quarterly", "Quartalsweise"),
            ("semiannual", "Halbjaehrlich"),
            ("annual", "Jaehrlich"),
            ("one_time", "Einmalig"),
        ],
        string="Zahlungsintervall",
        default="monthly",
    )
    termination_notice_months = fields.Integer(string="Kündigungsfrist (Monate)")
    auto_renew = fields.Boolean(string="Automatisch verlängern", default=False)
    renewal_period_months = fields.Integer(string="Verlängerungszeitraum (Monate)", default=12)
    cost_center = fields.Char(string="Kostenstelle")
    note = fields.Html(string="Vorlagennotizen")
    reminder_rule_ids = fields.Many2many(
        "contract.reminder.rule",
        "contract_template_reminder_rule_rel",
        "template_id",
        "rule_id",
        string="Erinnerungen",
    )

    def action_create_contract_from_template(self):
        self.ensure_one()
        context = {
            "default_name": self.name,
            "default_template_id": self.id,
            "default_contract_kind": self.contract_kind,
            "default_type_id": self.type_id.id,
            "default_category_id": self.category_id.id,
            "default_department_id": self.department_id.id,
            "default_responsible_user_id": self.responsible_user_id.id,
            "default_approval_user_id": self.approval_user_id.id,
            "default_manager_approval_user_id": self.manager_approval_user_id.id,
            "default_currency_id": self.currency_id.id,
            "default_contract_value": self.contract_value,
            "default_payment_interval": self.payment_interval,
            "default_termination_notice_months": self.termination_notice_months,
            "default_auto_renew": self.auto_renew,
            "default_renewal_period_months": self.renewal_period_months,
            "default_cost_center": self.cost_center,
            "default_note": self.note,
            "default_reminder_rule_ids": [(6, 0, self.reminder_rule_ids.ids)],
        }
        return {
            "type": "ir.actions.act_window",
            "name": "Neuer Vertrag aus Vorlage",
            "res_model": "contract.contract",
            "view_mode": "form",
            "target": "current",
            "context": context,
        }
