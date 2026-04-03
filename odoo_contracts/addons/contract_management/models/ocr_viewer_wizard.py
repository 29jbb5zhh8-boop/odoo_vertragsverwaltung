from odoo import api, fields, models


class ContractOcrViewerWizard(models.TransientModel):
    _name = "contract.ocr.viewer.wizard"
    _description = "OCR Viewer"

    ocr_text = fields.Text(string="OCR Ergebnis", readonly=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        contract_id = self.env.context.get("default_contract_id")
        if contract_id:
            contract = self.env["contract.contract"].browse(contract_id)
            res["ocr_text"] = contract.ocr_text_combined or ""
        return res
