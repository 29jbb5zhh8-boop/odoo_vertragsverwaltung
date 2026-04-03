from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ContractReminderSent(models.Model):
    _name = "contract.reminder.sent"
    _description = "Contract Reminder Sent"
    _order = "reminder_date desc"
    _sql_constraints = [
        (
            "contract_rule_date_unique",
            "unique(contract_id, rule_id, reminder_date)",
            "Diese Erinnerung wurde fuer den Vertrag bereits angelegt.",
        )
    ]

    contract_id = fields.Many2one(
        "contract.contract",
        string="Vertrag",
        required=True,
        ondelete="cascade",
    )
    rule_id = fields.Many2one(
        "contract.reminder.rule",
        string="Erinnerungsregel",
        required=True,
        ondelete="cascade",
    )
    reminder_date = fields.Date(string="Erinnerungsdatum", required=True)
    activity_id = fields.Many2one(
        "mail.activity",
        string="Aktivitaet",
        ondelete="set null",
    )

    @api.constrains("contract_id", "rule_id", "reminder_date")
    def _check_unique_reminder(self):
        for rec in self:
            if not rec.contract_id or not rec.rule_id or not rec.reminder_date:
                continue
            exists = self.search_count(
                [
                    ("id", "!=", rec.id),
                    ("contract_id", "=", rec.contract_id.id),
                    ("rule_id", "=", rec.rule_id.id),
                    ("reminder_date", "=", rec.reminder_date),
                ]
            )
            if exists:
                raise ValidationError("Diese Erinnerung wurde fuer den Vertrag bereits angelegt.")
