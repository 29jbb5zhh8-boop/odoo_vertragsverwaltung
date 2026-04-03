from odoo import api, fields, models


class ContractAttachmentRenameWizard(models.TransientModel):
    _name = "contract.attachment.rename.wizard"
    _description = "Attachment umbenennen"

    attachment_id = fields.Many2one("ir.attachment", string="Anhang", required=True, readonly=True)
    contract_id = fields.Many2one("contract.contract", string="Vertrag", readonly=True)
    current_name = fields.Char(string="Aktueller Name", readonly=True)
    new_name = fields.Char(string="Neuer Name", required=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        attachment_id = self.env.context.get("default_attachment_id")
        if attachment_id:
            attachment = self.env["ir.attachment"].browse(attachment_id)
            if attachment.exists():
                res.update(
                    {
                        "attachment_id": attachment.id,
                        "contract_id": attachment.res_id if attachment.res_model == "contract.contract" else False,
                        "current_name": attachment.name,
                        "new_name": attachment.name,
                    }
                )
        return res

    def action_apply(self):
        self.ensure_one()
        self.attachment_id.write({"name": self.new_name.strip()})
        return {"type": "ir.actions.act_window_close"}
