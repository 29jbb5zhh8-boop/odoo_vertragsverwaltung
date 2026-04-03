from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


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
    lock_type_id = fields.Boolean(string="Vertragstyp sperren", default=False)
    lock_category_id = fields.Boolean(string="Kategorie sperren", default=False)
    lock_department_id = fields.Boolean(string="Abteilung sperren", default=False)
    lock_responsible_user = fields.Boolean(string="Verantwortung sperren", default=False)
    lock_approval_chain = fields.Boolean(string="Freigabekette sperren", default=False)
    lock_cost_center = fields.Boolean(string="Kostenstelle sperren", default=False)
    lock_finance_terms = fields.Boolean(string="Konditionen sperren", default=False)
    lock_reminder_rules = fields.Boolean(string="Erinnerungen sperren", default=False)
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

    @api.constrains(
        "lock_type_id",
        "type_id",
        "lock_category_id",
        "category_id",
        "lock_department_id",
        "department_id",
        "lock_responsible_user",
        "responsible_user_id",
        "lock_approval_chain",
        "approval_user_id",
        "lock_cost_center",
        "cost_center",
        "lock_finance_terms",
        "contract_value",
        "payment_interval",
    )
    def _check_lock_configuration(self):
        for rec in self:
            errors = []
            if rec.lock_type_id and not rec.type_id:
                errors.append("Bei gesperrtem Vertragstyp muss ein Typ auf der Vorlage gesetzt sein.")
            if rec.lock_category_id and not rec.category_id:
                errors.append("Bei gesperrter Kategorie muss eine Kategorie auf der Vorlage gesetzt sein.")
            if rec.lock_department_id and not rec.department_id:
                errors.append("Bei gesperrter Abteilung muss eine Abteilung auf der Vorlage gesetzt sein.")
            if rec.lock_responsible_user and not rec.responsible_user_id:
                errors.append("Bei gesperrter Verantwortung muss ein Verantwortlicher gesetzt sein.")
            if rec.lock_approval_chain and not rec.approval_user_id:
                errors.append("Bei gesperrter Freigabekette muss mindestens ein Freigeber gesetzt sein.")
            if rec.lock_cost_center and not rec.cost_center:
                errors.append("Bei gesperrter Kostenstelle muss eine Kostenstelle gesetzt sein.")
            if rec.lock_finance_terms and (rec.contract_value < 0 or not rec.payment_interval):
                errors.append("Bei gesperrten Konditionen muessen Vertragswert und Zahlungsintervall gesetzt sein.")
            if errors:
                raise ValidationError("\n".join(errors))

    def _get_contract_kind_profile_values(self):
        self.ensure_one()
        values = {
            "require_partner": self.contract_kind != "other",
            "require_cost_center": self.contract_kind in {"supplier", "rent", "lease", "maintenance", "license", "insurance"},
            "require_dates": self.contract_kind in {"rent", "lease", "maintenance", "service", "license", "insurance"},
            "require_value": self.contract_kind != "other",
            "require_payment_interval": self.contract_kind in {"supplier", "customer", "rent", "lease", "maintenance", "service", "license", "insurance"},
        }
        if self.contract_kind == "customer":
            values["require_cost_center"] = False
        return values

    def action_apply_contract_kind_profile(self):
        for rec in self:
            rec.write(rec._get_contract_kind_profile_values())

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
