from odoo import fields, models


class DeviceDevice(models.Model):
    _name = "device.device"
    _description = "Asset"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name"

    active = fields.Boolean(default=True)
    name = fields.Char(string="Asset-Name", required=True, tracking=True)
    asset_tag = fields.Char(string="Asset-ID", tracking=True, index=True)
    asset_reference = fields.Char(string="Referenz", tracking=True)
    asset_type_id = fields.Many2one(
        "device.type",
        string="Asset-Typ",
        tracking=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Kunde",
        required=True,
        tracking=True,
        index=True,
    )
    site_id = fields.Many2one(
        "res.partner",
        string="Standort",
        domain="[('parent_id', '=', partner_id)]",
    )
    vendor_id = fields.Many2one(
        "res.partner",
        string="Lieferant",
    )
    serial_number = fields.Char(string="Seriennummer", tracking=True)
    manufacturer = fields.Char(string="Hersteller")
    model = fields.Char(string="Modell")
    state = fields.Selection(
        [
            ("in_use", "In Betrieb"),
            ("stock", "Lager"),
            ("broken", "Defekt"),
            ("retired", "Ausgemustert"),
        ],
        string="Status",
        default="in_use",
        tracking=True,
    )
    purchase_date = fields.Date(string="Kaufdatum")
    warranty_end = fields.Date(string="Garantie bis")
    hostname = fields.Char(string="Hostname")
    ip_address = fields.Char(string="IP-Adresse")
    mac_address = fields.Char(string="MAC-Adresse")
    os_name = fields.Char(string="Betriebssystem")
    os_version = fields.Char(string="OS-Version")
    firmware_version = fields.Char(string="Firmware-Version")
    image_1920 = fields.Image(string="Foto")
    note = fields.Text(string="Notizen")
    related_device_ids = fields.Many2many(
        "device.device",
        "device_management_related_device_rel",
        "device_id",
        "related_device_id",
        string="Siehe auch",
        help="Verknuepfte Geraete (Siehe auch).",
    )

    attachment_ids = fields.Many2many(
        "ir.attachment",
        "device_management_attachment_rel",
        "device_id",
        "attachment_id",
        string="Dokumente",
        help="Zugehoerige Dokumente zum Geraet.",
    )

    _sql_constraints = [
        ("asset_tag_uniq", "unique(asset_tag)", "Asset-ID muss eindeutig sein."),
    ]
