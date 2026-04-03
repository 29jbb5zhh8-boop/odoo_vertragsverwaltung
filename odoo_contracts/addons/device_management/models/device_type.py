from odoo import fields, models


class DeviceType(models.Model):
    _name = "device.type"
    _description = "Asset-Typ"
    _order = "sequence, name"

    name = fields.Char(string="Bezeichnung", required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    description = fields.Text(string="Beschreibung")
    image_1920 = fields.Image(string="Icon")
