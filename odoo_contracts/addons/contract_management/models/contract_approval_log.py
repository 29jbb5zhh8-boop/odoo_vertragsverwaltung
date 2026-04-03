from odoo import fields, models


class ContractApprovalLog(models.Model):
    _name = "contract.approval.log"
    _description = "Contract Approval Log"
    _order = "decided_at desc, id desc"

    contract_id = fields.Many2one(
        "contract.contract",
        string="Vertrag",
        required=True,
        ondelete="cascade",
    )
    contract_number = fields.Char(related="contract_id.contract_number", string="Vertragsnummer", store=True)
    stage = fields.Selection(
        [
            ("approval", "Fachfreigabe"),
            ("manager", "Manager-Freigabe"),
        ],
        string="Freigabestufe",
        required=True,
    )
    decision = fields.Selection(
        [
            ("submitted", "Eingereicht"),
            ("approved", "Freigegeben"),
            ("rejected", "Abgelehnt"),
            ("escalated", "Eskaliert"),
        ],
        string="Entscheidung",
        required=True,
    )
    actor_user_id = fields.Many2one("res.users", string="Ausgeloest von", required=True)
    assigned_user_id = fields.Many2one("res.users", string="Zugewiesen an")
    decision_comment = fields.Text(string="Kommentar")
    decided_at = fields.Datetime(string="Zeitpunkt", required=True, default=fields.Datetime.now)
    approval_state_after = fields.Selection(
        [
            ("draft", "In Bearbeitung"),
            ("pending", "Zur Freigabe"),
            ("pending_manager", "Zur Manager-Freigabe"),
            ("approved", "Freigegeben"),
            ("rejected", "Abgelehnt"),
        ],
        string="Status danach",
        required=True,
    )
    contract_value = fields.Monetary(
        string="Vertragswert",
        currency_field="currency_id",
        related="contract_id.contract_value",
        store=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Waehrung",
        related="contract_id.currency_id",
        store=True,
    )
