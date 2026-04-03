from odoo import fields, models


class ContractCategory(models.Model):
    _name = "contract.category"
    _description = "Contract Category"

    name = fields.Char(string="Vertragskategorie", required=True, translate=True)
    active = fields.Boolean(default=True)
