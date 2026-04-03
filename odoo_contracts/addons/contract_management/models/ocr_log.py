from odoo import fields, models


class ContractOcrLog(models.Model):
    _name = "contract.ocr.log"
    _description = "OCR Log"
    _order = "create_date desc"

    attachment_id = fields.Many2one("ir.attachment", string="Anhang", ondelete="cascade")
    contract_id = fields.Many2one("contract.contract", string="Vertrag", ondelete="cascade")
    ocr_state = fields.Selection(
        [
            ("none", "Nicht gequeued"),
            ("pending", "Wartet"),
            ("done", "Fertig"),
            ("error", "Fehler"),
        ],
        string="OCR Status",
        default="none",
        index=True,
    )
    ocr_error = fields.Text(string="OCR Fehler")
    ocr_text = fields.Text(string="OCR Ergebnis")
    create_date = fields.Datetime(string="Zeitpunkt", readonly=True)
