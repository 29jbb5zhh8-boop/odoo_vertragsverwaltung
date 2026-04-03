from odoo import fields, models


class ContractCancelWizard(models.TransientModel):
    _name = "contract.cancel.wizard"
    _description = "Contract Cancel Wizard"

    contract_id = fields.Many2one("contract.contract", required=True)
    reason = fields.Text(string="Kündigungsgrund", required=True)

    def action_confirm_cancel(self):
        self.ensure_one()
        contract = self.contract_id
        contract.write({
            "state": "cancelled",
            "cancellation_reason": self.reason,
        })
        contract.message_post(body=f"Vertrag gekündigt. Grund: {self.reason}")
        self.env["contract.timeline"].create(
            {
                "contract_id": contract.id,
                "event_type": "cancel",
                "message": f"Kündigung: {self.reason}",
                "user_id": self.env.user.id,
            }
        )
        return {"type": "ir.actions.act_window_close"}
