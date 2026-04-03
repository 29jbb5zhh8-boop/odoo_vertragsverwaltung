from odoo import fields, models


class ContractTimeline(models.Model):
    _name = "contract.timeline"
    _description = "Contract Timeline"
    _order = "event_date desc, id desc"

    contract_id = fields.Many2one("contract.contract", required=True, ondelete="cascade")
    event_date = fields.Datetime(string="Datum", required=True, default=fields.Datetime.now)
    user_id = fields.Many2one("res.users", string="Benutzer")
    event_type = fields.Selection(
        [
            ("status", "Status"),
            ("date", "Datum"),
            ("attachment", "Dokument"),
            ("reminder", "Erinnerung"),
            ("renew", "Verlängerung"),
            ("cancel", "Kündigung"),
            ("note", "Notiz"),
        ],
        string="Typ",
        required=True,
    )
    message = fields.Char(string="Eintrag", required=True)
