from odoo import fields, models
from odoo.exceptions import UserError


class ContractTemplate(models.Model):
    _name = "contract.template"
    _description = "Contract Template"
    _order = "name"

    name = fields.Char(string="Vorlagenname", required=True, translate=True)
    active = fields.Boolean(default=True)
    approval_state = fields.Selection(
        [
            ("draft", "Entwurf"),
            ("approved", "Freigegeben"),
            ("rejected", "Abgelehnt"),
        ],
        string="Template-Status",
        default="draft",
    )
    approved_by_id = fields.Many2one("res.users", string="Freigegeben von", readonly=True)
    approved_at = fields.Datetime(string="Freigegeben am", readonly=True)
    rejection_reason = fields.Text(string="Ablehnungsgrund", readonly=True)
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
    clause_text = fields.Html(string="Standardklauseln")
    require_partner = fields.Boolean(string="Partner verpflichtend", default=True)
    require_cost_center = fields.Boolean(string="Kostenstelle verpflichtend", default=False)
    require_dates = fields.Boolean(string="Start- und Enddatum verpflichtend", default=False)
    require_value = fields.Boolean(string="Vertragswert verpflichtend", default=True)
    require_payment_interval = fields.Boolean(
        string="Zahlungsintervall verpflichtend",
        default=True,
    )
    template_attachment_ids = fields.Many2many(
        "ir.attachment",
        "contract_template_attachment_rel",
        "template_id",
        "attachment_id",
        string="Dokumentenpaket",
    )
    reminder_rule_ids = fields.Many2many(
        "contract.reminder.rule",
        "contract_template_reminder_rule_rel",
        "template_id",
        "rule_id",
        string="Erinnerungen",
    )

    def action_approve_template(self):
        for rec in self:
            if not self.env.user.has_group("contract_management.group_contract_manager"):
                raise UserError("Nur Vertragsmanager duerfen Vorlagen freigeben.")
            rec.write(
                {
                    "approval_state": "approved",
                    "approved_by_id": self.env.user.id,
                    "approved_at": fields.Datetime.now(),
                    "rejection_reason": False,
                }
            )

    def action_reject_template(self):
        for rec in self:
            if not self.env.user.has_group("contract_management.group_contract_manager"):
                raise UserError("Nur Vertragsmanager duerfen Vorlagen ablehnen.")
            rec.write(
                {
                    "approval_state": "rejected",
                    "approved_by_id": False,
                    "approved_at": False,
                    "rejection_reason": "Vorlage manuell abgelehnt.",
                }
            )

    def action_reset_template_draft(self):
        self.write(
            {
                "approval_state": "draft",
                "approved_by_id": False,
                "approved_at": False,
                "rejection_reason": False,
            }
        )

    def action_create_contract_from_template(self):
        self.ensure_one()
        if self.approval_state != "approved":
            raise UserError("Nur freigegebene Vorlagen duerfen fuer neue Vertraege verwendet werden.")
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
            "default_note": self.clause_text,
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
