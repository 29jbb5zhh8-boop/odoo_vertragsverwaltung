from odoo import fields, models


class ContractType(models.Model):
    _name = "contract.type"
    _description = "Contract Type"

    name = fields.Char(string="Vertragstyp", required=True, translate=True)
    active = fields.Boolean(default=True)
