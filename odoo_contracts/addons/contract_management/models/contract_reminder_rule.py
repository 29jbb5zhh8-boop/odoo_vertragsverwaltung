from odoo import fields, models


class ContractReminderRule(models.Model):
    _name = "contract.reminder.rule"
    _description = "Contract Reminder Rule"
    _order = "days_before desc"

    name = fields.Char(string="Bezeichnung", required=True, translate=True)
    days_before = fields.Integer(string="Tage vor Ablauf", required=True)
    active = fields.Boolean(default=True)
