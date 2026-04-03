from odoo import api, fields, models
from odoo.exceptions import UserError


class ContractApprovalWizard(models.TransientModel):
    _name = "contract.approval.wizard"
    _description = "Contract Approval Wizard"

    contract_id = fields.Many2one("contract.contract", required=True, readonly=True)
    decision = fields.Selection(
        [
            ("approve", "Freigeben"),
            ("reject", "Ablehnen"),
        ],
        required=True,
        readonly=True,
    )
    comment = fields.Text(string="Kommentar")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        contract_id = self.env.context.get("default_contract_id")
        decision = self.env.context.get("default_decision")
        if contract_id:
            res["contract_id"] = contract_id
        if decision:
            res["decision"] = decision
        return res

    def action_confirm(self):
        self.ensure_one()
        if self.decision == "reject" and not (self.comment or "").strip():
            raise UserError("Bitte einen Ablehnungsgrund angeben.")
        self.contract_id.action_apply_approval_decision(
            self.decision,
            comment=self.comment,
        )
        return {"type": "ir.actions.act_window_close"}
