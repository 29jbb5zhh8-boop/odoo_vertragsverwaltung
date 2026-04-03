import base64

from odoo import api, fields, models
from odoo.tools import html2plaintext
from odoo.exceptions import UserError, ValidationError
from odoo.tools.pdf import merge_pdf


class ContractContract(models.Model):
    _name = "contract.contract"
    _description = "Contract"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "name"

    contract_number = fields.Char(
        string="Vertragsnummer",
        readonly=True,
        copy=False,
        index=True,
    )
    name = fields.Char(string="Vertragstitel", required=True, tracking=True)
    partner_id = fields.Many2one(
        "res.partner",
        string="Vertragspartner",
        tracking=True,
    )
    type_id = fields.Many2one(
        "contract.type",
        string="Vertragstyp",
        tracking=True,
    )
    contract_kind = fields.Selection(
        [
            ("supplier", "Lieferant"),
            ("customer", "Kunde"),
            ("rent", "Miete"),
            ("lease", "Leasing"),
            ("maintenance", "Wartung"),
            ("service", "Dienstleistung"),
            ("license", "Lizenz"),
            ("insurance", "Versicherung"),
            ("other", "Sonstiges"),
        ],
        string="Vertragsart",
        default="supplier",
        required=True,
        tracking=True,
    )
    category_id = fields.Many2one(
        "contract.category",
        string="Vertragskategorie",
        tracking=True,
    )
    responsible_user_id = fields.Many2one(
        "res.users",
        string="Verantwortlich",
        tracking=True,
    )
    approval_user_id = fields.Many2one(
        "res.users",
        string="Freigeber",
        tracking=True,
    )
    manager_approval_user_id = fields.Many2one(
        "res.users",
        string="Manager-Freigeber",
        tracking=True,
    )
    department_id = fields.Many2one(
        "hr.department",
        string="Interne Abteilung",
        tracking=True,
    )
    cost_center = fields.Char(
        string="Kostenstelle",
        tracking=True,
    )
    start_date = fields.Date(string="Startdatum", tracking=True)
    end_date = fields.Date(string="Enddatum", tracking=True)
    currency_id = fields.Many2one(
        "res.currency",
        string="Waehrung",
        required=True,
        default=lambda self: self.env.company.currency_id.id,
        tracking=True,
    )
    contract_value = fields.Monetary(
        string="Vertragswert",
        currency_field="currency_id",
        tracking=True,
    )
    normalized_monthly_value = fields.Monetary(
        string="Monatswert",
        currency_field="currency_id",
        compute="_compute_normalized_values",
        store=True,
    )
    normalized_annual_value = fields.Monetary(
        string="Jahreswert",
        currency_field="currency_id",
        compute="_compute_normalized_values",
        store=True,
    )
    payment_interval = fields.Selection(
        [
            ("monthly", "Monatlich"),
            ("quarterly", "Quartalsweise"),
            ("semiannual", "Halbjaehrlich"),
            ("annual", "Jaehrlich"),
            ("one_time", "Einmalig"),
        ],
        string="Zahlungsintervall",
        default="monthly",
        tracking=True,
    )
    termination_notice_months = fields.Integer(
        string="Kündigungsfrist (Monate)",
        help="Kündigungsfrist in Monaten.",
        default=0,
    )
    auto_renew = fields.Boolean(string="Automatisch verlängern", default=False)
    renewal_period_months = fields.Integer(
        string="Verlängerungszeitraum (Monate)",
        default=12,
        help="Zeitraum der automatischen Verlängerung in Monaten.",
    )
    next_end_date = fields.Date(
        string="Nächstes Enddatum",
        compute="_compute_next_end_date",
        store=True,
    )
    expiry_status = fields.Selection(
        [
            ("green", "Grün"),
            ("yellow", "Gelb"),
            ("red", "Rot"),
        ],
        string="Ampel",
        compute="_compute_expiry_status",
        store=True,
    )
    earliest_termination_date = fields.Date(
        string="Frühest. kündbar ab",
        compute="_compute_earliest_termination_date",
        store=True,
    )
    state = fields.Selection(
        [
            ("draft", "Entwurf"),
            ("active", "Aktiv"),
            ("expiring", "Läuft bald ab"),
            ("expired", "Abgelaufen"),
            ("cancelled", "Gekündigt"),
        ],
        string="Status",
        default="draft",
        tracking=True,
    )
    approval_state = fields.Selection(
        [
            ("draft", "In Bearbeitung"),
            ("pending", "Zur Freigabe"),
            ("pending_manager", "Zur Manager-Freigabe"),
            ("approved", "Freigegeben"),
            ("rejected", "Abgelehnt"),
        ],
        string="Freigabe",
        default="draft",
        tracking=True,
    )
    submitted_for_approval_at = fields.Datetime(
        string="Eingereicht am",
        readonly=True,
    )
    approved_at = fields.Datetime(
        string="Freigegeben am",
        readonly=True,
    )
    approval_comment = fields.Text(
        string="Freigabekommentar",
        readonly=True,
    )
    manager_approval_comment = fields.Text(
        string="Manager-Kommentar",
        readonly=True,
    )
    rejection_reason = fields.Text(
        string="Ablehnungsgrund",
        readonly=True,
    )
    approval_decided_by_id = fields.Many2one(
        "res.users",
        string="Freigabe entschieden von",
        readonly=True,
    )
    manager_approved_at = fields.Datetime(
        string="Manager-freigegeben am",
        readonly=True,
    )
    requires_manager_approval = fields.Boolean(
        string="Manager-Freigabe erforderlich",
        compute="_compute_requires_manager_approval",
        store=True,
    )
    note = fields.Html(string="Notizen")
    fulltext = fields.Text(string="Volltext", compute="_compute_fulltext", store=True, index=True)

    ocr_text_combined = fields.Text(
        string="OCR Ergebnis",
        compute="_compute_ocr_text_combined",
    )
    cancellation_reason = fields.Text(string="Kündigungsgrund", readonly=True)
    show_chatter = fields.Boolean(string="Chatter anzeigen", default=True)

    attachment_ids = fields.Many2many(
        "ir.attachment",
        "contract_attachment_rel",
        "contract_id",
        "attachment_id",
        string="Anhänge",
        help="Vertragsdokumente (PDF etc.) anhängen.",
        domain="[('mimetype', '=', 'application/pdf')]",
    )

    reminder_rule_ids = fields.Many2many(
        "contract.reminder.rule",
        "contract_reminder_rule_rel",
        "contract_id",
        "rule_id",
        string="Erinnerungen",
        help="Erinnerungen vor Ablauf dieses Vertrags.",
        default=lambda self: self.env["contract.reminder.rule"].search([("active", "=", True)]),
    )

    reminder_sent_ids = fields.One2many(
        "contract.reminder.sent",
        "contract_id",
        string="Gesendete Erinnerungen",
    )
    timeline_ids = fields.One2many(
        "contract.timeline",
        "contract_id",
        string="Timeline",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("contract_number"):
                seq = self.env["ir.sequence"].sudo().next_by_code("contract.contract")
                vals["contract_number"] = seq or "V-00000"
            if not vals.get("responsible_user_id"):
                vals["responsible_user_id"] = self.env.user.id
        return super().create(vals_list)

    def name_get(self):
        result = []
        for rec in self:
            number = rec.contract_number
            title = rec.name or ""
            if number and title:
                display = f"[{number}] {title}"
            elif number:
                display = number
            else:
                display = title
            result.append((rec.id, display))
        return result

    def _assign_missing_contract_numbers(self):
        missing = self.sudo().search([("contract_number", "in", [False, ""])])
        for rec in missing:
            rec.contract_number = self.env["ir.sequence"].next_by_code(
                "contract.contract"
            )

    def init(self):
        super().init()
        self._assign_missing_contract_numbers()

    @api.constrains("start_date", "end_date")
    def _check_dates(self):
        for rec in self:
            if rec.start_date and rec.end_date and rec.end_date < rec.start_date:
                raise ValidationError("Enddatum muss nach dem Startdatum liegen.")

    @api.constrains("contract_value")
    def _check_contract_value(self):
        for rec in self:
            if rec.contract_value and rec.contract_value < 0:
                raise ValidationError("Der Vertragswert darf nicht negativ sein.")

    @api.constrains(
        "contract_kind",
        "partner_id",
        "contract_value",
        "payment_interval",
        "start_date",
        "end_date",
    )
    def _check_contract_kind_requirements(self):
        value_required_kinds = {
            "supplier",
            "customer",
            "rent",
            "lease",
            "maintenance",
            "service",
            "license",
            "insurance",
        }
        dated_kinds = {"rent", "lease", "maintenance", "service", "license", "insurance"}
        for rec in self:
            errors = []
            if rec.contract_kind != "other" and not rec.partner_id:
                errors.append("Vertragspartner ist fuer diese Vertragsart verpflichtend.")
            if rec.contract_kind in value_required_kinds and not rec.contract_value:
                errors.append("Vertragswert ist fuer diese Vertragsart verpflichtend.")
            if rec.contract_kind in value_required_kinds and not rec.payment_interval:
                errors.append("Zahlungsintervall ist fuer diese Vertragsart verpflichtend.")
            if rec.contract_kind in dated_kinds and not rec.start_date:
                errors.append("Startdatum ist fuer diese Vertragsart verpflichtend.")
            if rec.contract_kind in dated_kinds and not rec.end_date:
                errors.append("Enddatum ist fuer diese Vertragsart verpflichtend.")
            if errors:
                raise ValidationError("\n".join(errors))

    def _get_manager_approval_threshold(self):
        value = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("contract_management.manager_approval_threshold", "10000")
        )
        try:
            return float(value)
        except (TypeError, ValueError):
            return 10000.0

    @api.depends("contract_value", "currency_id")
    def _compute_requires_manager_approval(self):
        threshold = self._get_manager_approval_threshold()
        company_currency = self.env.company.currency_id
        for rec in self:
            if not rec.contract_value or not rec.currency_id or not company_currency:
                rec.requires_manager_approval = False
                continue
            amount_company_currency = rec.currency_id._convert(
                rec.contract_value,
                company_currency,
                self.env.company,
                rec.start_date or fields.Date.context_today(rec),
            )
            rec.requires_manager_approval = amount_company_currency >= threshold

    @api.depends("contract_value", "payment_interval")
    def _compute_normalized_values(self):
        interval_divisors = {
            "monthly": 1.0,
            "quarterly": 3.0,
            "semiannual": 6.0,
            "annual": 12.0,
        }
        for rec in self:
            value = rec.contract_value or 0.0
            if not value:
                rec.normalized_monthly_value = 0.0
                rec.normalized_annual_value = 0.0
                continue
            if rec.payment_interval == "one_time":
                rec.normalized_monthly_value = 0.0
                rec.normalized_annual_value = value
                continue
            divisor = interval_divisors.get(rec.payment_interval, 1.0)
            monthly_value = value / divisor
            rec.normalized_monthly_value = monthly_value
            rec.normalized_annual_value = monthly_value * 12.0

    @api.depends("end_date", "termination_notice_months")
    def _compute_earliest_termination_date(self):
        for rec in self:
            if rec.end_date and rec.termination_notice_months and rec.termination_notice_months > 0:
                rec.earliest_termination_date = fields.Date.subtract(
                    rec.end_date, months=rec.termination_notice_months
                )
            else:
                rec.earliest_termination_date = False

    @api.depends("end_date", "renewal_period_months")
    def _compute_next_end_date(self):
        for rec in self:
            if rec.end_date and rec.renewal_period_months and rec.renewal_period_months > 0:
                rec.next_end_date = fields.Date.add(
                    rec.end_date, months=rec.renewal_period_months
                )
            else:
                rec.next_end_date = False

    @api.depends("end_date")
    def _compute_expiry_status(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if not rec.end_date:
                rec.expiry_status = False
                continue
            days_left = (rec.end_date - today).days
            if days_left <= 30:
                rec.expiry_status = "red"
            elif days_left <= 90:
                rec.expiry_status = "yellow"
            else:
                rec.expiry_status = "green"

    @api.constrains("attachment_ids")
    def _check_attachments_pdf(self):
        for rec in self:
            invalid = rec.attachment_ids.filtered(
                lambda a: a.mimetype and a.mimetype != "application/pdf" and not a.mimetype.startswith("image/")
            )
            if invalid:
                raise ValidationError("Nur PDF- oder Bild-Dateien sind erlaubt.")

    @api.depends("note", "attachment_ids.index_content", "attachment_ids.show_in_contract")
    def _compute_fulltext(self):
        for rec in self:
            note_text = html2plaintext(rec.note or "")
            attach_texts = rec.attachment_ids.filtered(lambda a: a.show_in_contract).mapped(
                "index_content"
            )
            parts = [note_text] + [t for t in attach_texts if t]
            rec.fulltext = "\n".join(parts).strip()

    @api.depends("attachment_ids.ocr_text", "attachment_ids.show_in_contract", "attachment_ids.is_current")
    def _compute_ocr_text_combined(self):
        for rec in self:
            visible_attachments = rec.attachment_ids.filtered(
                lambda a: a.show_in_contract and a.ocr_text
            )
            if not visible_attachments:
                visible_attachments = rec.attachment_ids.filtered(
                    lambda a: a.is_current and a.ocr_text
                )
            texts = visible_attachments.mapped("ocr_text")
            rec.ocr_text_combined = "\n\n".join([text for text in texts if text]).strip()


    def action_activate(self):
        for rec in self:
            if rec.approval_state != "approved":
                raise UserError("Der Vertrag muss vor der Aktivierung freigegeben werden.")
        self.write({"state": "active"})

    def action_cancel(self):
        self.write({"state": "cancelled"})

    def action_set_expired(self):
        self.write({"state": "expired"})

    def action_reset_draft(self):
        self._close_approval_activities()
        self.write(
            {
                "state": "draft",
                "approval_state": "draft",
                "submitted_for_approval_at": False,
                "approved_at": False,
                "approval_comment": False,
                "manager_approval_comment": False,
                "rejection_reason": False,
                "approval_decided_by_id": False,
                "manager_approved_at": False,
            }
        )

    def _check_can_approve(self):
        self.ensure_one()
        if self.approval_state == "pending_manager":
            if self.env.user.has_group("contract_management.group_contract_manager"):
                return
            if self.manager_approval_user_id == self.env.user:
                return
            raise UserError(
                "Nur der zugewiesene Manager-Freigeber oder ein Vertragsmanager darf in dieser Stufe entscheiden."
            )
        if self.env.user.has_group("contract_management.group_contract_manager"):
            return
        if self.approval_user_id != self.env.user:
            raise UserError("Nur der zugewiesene Freigeber oder ein Vertragsmanager darf freigeben.")

    def _get_approval_activity_type(self):
        return self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)

    def _close_approval_activities(self, feedback=None):
        activity_type = self._get_approval_activity_type()
        for rec in self:
            domain = [
                ("res_model", "=", "contract.contract"),
                ("res_id", "=", rec.id),
                ("summary", "ilike", "Freigabe:"),
            ]
            if activity_type:
                domain.append(("activity_type_id", "=", activity_type.id))
            activities = self.env["mail.activity"].sudo().search(domain)
            if not activities:
                continue
            if hasattr(activities, "action_feedback"):
                activities.action_feedback(feedback=feedback or "")
            else:
                activities.unlink()

    def _create_approval_activity(self, stage="approval"):
        activity_type = self._get_approval_activity_type()
        if not activity_type:
            return
        model_id = self.env["ir.model"]._get_id("contract.contract")
        for rec in self:
            if stage == "manager":
                target_user = rec.manager_approval_user_id
                summary = "Freigabe: Manager-Freigabe pruefen"
                note = (
                    f"Bitte hochvolumigen Vertrag {rec.display_name} als Manager pruefen."
                )
            else:
                target_user = rec.approval_user_id
                summary = "Freigabe: Vertrag pruefen"
                note = (
                    f"Bitte Vertrag {rec.display_name} pruefen und freigeben oder ablehnen."
                )
            if not target_user:
                continue
            self.env["mail.activity"].sudo().create(
                {
                    "activity_type_id": activity_type.id,
                    "summary": summary,
                    "note": note,
                    "date_deadline": fields.Date.context_today(rec),
                    "res_model_id": model_id,
                    "res_id": rec.id,
                    "user_id": target_user.id,
                }
            )

    def action_submit_for_approval(self):
        for rec in self:
            if rec.approval_state not in ("draft", "rejected"):
                raise UserError("Nur Entwuerfe oder abgelehnte Vertraege koennen eingereicht werden.")
            if not rec.approval_user_id:
                raise UserError("Bitte zuerst einen Freigeber hinterlegen.")
            if (
                rec.requires_manager_approval
                and not rec.manager_approval_user_id
                and not rec.approval_user_id.has_group("contract_management.group_contract_manager")
            ):
                raise UserError(
                    "Ab diesem Vertragswert ist ein Manager-Freigeber erforderlich."
                )
            rec._close_approval_activities()
            rec.write(
                {
                    "approval_state": "pending",
                    "submitted_for_approval_at": fields.Datetime.now(),
                    "approved_at": False,
                    "approval_comment": False,
                    "manager_approval_comment": False,
                    "rejection_reason": False,
                    "approval_decided_by_id": False,
                    "manager_approved_at": False,
                }
            )
            rec._create_approval_activity()
            rec.message_post(
                body=f"Vertrag zur Freigabe eingereicht an {rec.approval_user_id.display_name}."
            )
            self.env["contract.timeline"].create(
                {
                    "contract_id": rec.id,
                    "event_type": "status",
                    "message": f"Zur Freigabe eingereicht an {rec.approval_user_id.display_name}",
                    "user_id": self.env.user.id,
                }
            )

    def action_open_approve_wizard(self):
        self.ensure_one()
        self._check_can_approve()
        if self.approval_state not in ("pending", "pending_manager"):
            raise UserError("Nur Vertraege in einem Freigabeschritt koennen freigegeben werden.")
        return {
            "type": "ir.actions.act_window",
            "name": "Vertrag freigeben",
            "res_model": "contract.approval.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_contract_id": self.id,
                "default_decision": "approve",
            },
        }

    def action_open_reject_wizard(self):
        self.ensure_one()
        self._check_can_approve()
        if self.approval_state not in ("pending", "pending_manager"):
            raise UserError("Nur Vertraege in einem Freigabeschritt koennen abgelehnt werden.")
        return {
            "type": "ir.actions.act_window",
            "name": "Vertrag ablehnen",
            "res_model": "contract.approval.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_contract_id": self.id,
                "default_decision": "reject",
            },
        }

    def action_apply_approval_decision(self, decision, comment=False):
        for rec in self:
            if rec.approval_state not in ("pending", "pending_manager"):
                raise UserError("Nur Vertraege im Status 'Zur Freigabe' koennen bearbeitet werden.")
            rec._check_can_approve()
            clean_comment = (comment or "").strip()
            if decision == "reject" and not clean_comment:
                raise UserError("Bei einer Ablehnung ist ein Kommentar verpflichtend.")
            values = {}
            if decision == "approve":
                if rec.approval_state == "pending" and rec.requires_manager_approval and not self.env.user.has_group(
                    "contract_management.group_contract_manager"
                ):
                    values.update(
                        {
                            "approval_state": "pending_manager",
                            "approval_comment": clean_comment or False,
                            "rejection_reason": False,
                            "approval_decided_by_id": self.env.user.id,
                            "approved_at": False,
                            "manager_approval_comment": False,
                            "manager_approved_at": False,
                        }
                    )
                    feedback = clean_comment or "Vorpruefung abgeschlossen."
                    message = "Vorpruefung abgeschlossen, wartet auf Manager-Freigabe"
                    rec.write(values)
                    rec._close_approval_activities(feedback=feedback)
                    rec._create_approval_activity(stage="manager")
                else:
                    values.update(
                        {
                            "approval_state": "approved",
                            "approved_at": fields.Datetime.now(),
                            "rejection_reason": False,
                            "approval_decided_by_id": self.env.user.id,
                        }
                    )
                    if rec.approval_state == "pending_manager":
                        values.update(
                            {
                                "manager_approval_comment": clean_comment or False,
                                "manager_approved_at": fields.Datetime.now(),
                            }
                        )
                    else:
                        values.update(
                            {
                                "approval_comment": clean_comment or False,
                                "manager_approval_comment": False,
                                "manager_approved_at": False,
                            }
                        )
                    feedback = clean_comment or "Vertrag freigegeben."
                    message = "Vertrag freigegeben"
                    rec.write(values)
                    rec._close_approval_activities(feedback=feedback)
            elif decision == "reject":
                values.update(
                    {
                        "approval_state": "rejected",
                        "approved_at": False,
                        "rejection_reason": clean_comment,
                        "approval_decided_by_id": self.env.user.id,
                        "manager_approved_at": False,
                    }
                )
                if rec.approval_state == "pending_manager":
                    values.update(
                        {
                            "manager_approval_comment": False,
                        }
                    )
                else:
                    values.update(
                        {
                            "approval_comment": False,
                            "manager_approval_comment": False,
                        }
                    )
                feedback = clean_comment
                message = f"Vertrag abgelehnt: {clean_comment}"
                rec.write(values)
                rec._close_approval_activities(feedback=feedback)
            else:
                raise UserError("Unbekannte Freigabeentscheidung.")
            rec.message_post(body=message)
            self.env["contract.timeline"].create(
                {
                    "contract_id": rec.id,
                    "event_type": "status",
                    "message": message,
                    "user_id": self.env.user.id,
                }
            )


    def action_open_ocr_viewer(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "OCR Ergebnis",
            "res_model": "contract.ocr.viewer.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_contract_id": self.id},
        }

    def action_print_pdf_with_attachments(self):
        self.ensure_one()
        report_ref = "contract_management.action_report_contract"
        pdf_content, _ = self.env["ir.actions.report"]._render_qweb_pdf(report_ref, res_ids=[self.id])

        attachments = self.attachment_ids.filtered(
            lambda a: a.show_in_contract and a.mimetype == "application/pdf"
        )
        pdf_parts = [pdf_content]
        for att in attachments:
            if not att.datas:
                continue
            pdf_parts.append(base64.b64decode(att.datas))

        merged_pdf = merge_pdf(pdf_parts) if len(pdf_parts) > 1 else pdf_content
        filename = f"Vertrag - {self.name or self.display_name}.pdf"
        attachment = self.env["ir.attachment"].with_context(
            skip_contract_attachment=True
        ).create(
            {
                "name": filename,
                "type": "binary",
                "datas": base64.b64encode(merged_pdf),
                "mimetype": "application/pdf",
                "res_model": "contract.contract",
                "res_id": self.id,
            }
        )
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{attachment.id}?download=true",
            "target": "self",
        }

    def write(self, vals):
        old_states = {}
        old_approval_states = {}
        old_dates = {}
        old_misc = {}
        to_log = []
        if "state" in vals:
            for rec in self:
                old_states[rec.id] = rec.state
        if "approval_state" in vals:
            for rec in self:
                old_approval_states[rec.id] = rec.approval_state
        if "start_date" in vals or "end_date" in vals:
            for rec in self:
                old_dates[rec.id] = (rec.start_date, rec.end_date)
        if (
            "type_id" in vals
            or "partner_id" in vals
            or "responsible_user_id" in vals
            or "approval_user_id" in vals
            or "manager_approval_user_id" in vals
        ):
            for rec in self:
                old_misc[rec.id] = (
                    rec.type_id,
                    rec.partner_id,
                    rec.responsible_user_id,
                    rec.approval_user_id,
                    rec.manager_approval_user_id,
                )
        res = super().write(vals)
        if "state" in vals:
            for rec in self:
                old = old_states.get(rec.id)
                new = rec.state
                if old and old != new:
                    rec.message_post(
                        body=f"Status geaendert: {dict(self._fields['state'].selection).get(old)} → {dict(self._fields['state'].selection).get(new)}"
                    )
                    to_log.append((rec, "status", f"Status: {dict(self._fields['state'].selection).get(old)} → {dict(self._fields['state'].selection).get(new)}"))
        if "approval_state" in vals:
            for rec in self:
                old = old_approval_states.get(rec.id)
                new = rec.approval_state
                if old and old != new:
                    rec.message_post(
                        body=(
                            "Freigabe geaendert: "
                            f"{dict(self._fields['approval_state'].selection).get(old)} → "
                            f"{dict(self._fields['approval_state'].selection).get(new)}"
                        )
                    )
                    to_log.append(
                        (
                            rec,
                            "status",
                            "Freigabe: "
                            f"{dict(self._fields['approval_state'].selection).get(old)} → "
                            f"{dict(self._fields['approval_state'].selection).get(new)}",
                        )
                    )
        if "start_date" in vals or "end_date" in vals:
            for rec in self:
                old_start, old_end = old_dates.get(rec.id, (False, False))
                if old_start != rec.start_date:
                    rec.message_post(
                        body=f"Startdatum geaendert: {old_start or '-'} → {rec.start_date or '-'}"
                    )
                    to_log.append((rec, "date", f"Startdatum: {old_start or '-'} → {rec.start_date or '-'}"))
                if old_end != rec.end_date:
                    rec.message_post(
                        body=f"Enddatum geaendert: {old_end or '-'} → {rec.end_date or '-'}"
                    )
                    to_log.append((rec, "date", f"Enddatum: {old_end or '-'} → {rec.end_date or '-'}"))
        if (
            "type_id" in vals
            or "partner_id" in vals
            or "responsible_user_id" in vals
            or "approval_user_id" in vals
            or "manager_approval_user_id" in vals
        ):
            for rec in self:
                old_type, old_partner, old_resp, old_approver, old_manager_approver = old_misc.get(
                    rec.id, (False, False, False, False, False)
                )
                if old_type != rec.type_id:
                    rec.message_post(
                        body=f"Vertragstyp geaendert: {old_type.display_name if old_type else '-'} → {rec.type_id.display_name if rec.type_id else '-'}"
                    )
                if old_partner != rec.partner_id:
                    rec.message_post(
                        body=f"Vertragspartner geaendert: {old_partner.display_name if old_partner else '-'} → {rec.partner_id.display_name if rec.partner_id else '-'}"
                    )
                if old_resp != rec.responsible_user_id:
                    rec.message_post(
                        body=f"Verantwortlich geaendert: {old_resp.display_name if old_resp else '-'} → {rec.responsible_user_id.display_name if rec.responsible_user_id else '-'}"
                    )
                if old_approver != rec.approval_user_id:
                    rec.message_post(
                        body=f"Freigeber geaendert: {old_approver.display_name if old_approver else '-'} → {rec.approval_user_id.display_name if rec.approval_user_id else '-'}"
                    )
                if old_manager_approver != rec.manager_approval_user_id:
                    rec.message_post(
                        body=f"Manager-Freigeber geaendert: {old_manager_approver.display_name if old_manager_approver else '-'} → {rec.manager_approval_user_id.display_name if rec.manager_approval_user_id else '-'}"
                    )
        for rec, etype, msg in to_log:
            self.env["contract.timeline"].create(
                {
                    "contract_id": rec.id,
                    "event_type": etype,
                    "message": msg,
                    "user_id": self.env.user.id,
                }
            )
        return res

    def action_toggle_chatter(self):
        for rec in self:
            rec.show_chatter = not rec.show_chatter

    def _get_reminder_user(self):
        self.ensure_one()
        if self.responsible_user_id and self.responsible_user_id.active:
            return self.responsible_user_id
        if self.create_uid and self.create_uid.active:
            return self.create_uid
        return self.env.user


    def _cron_create_reminders(self):
        today = fields.Date.context_today(self)
        default_rules = self.env["contract.reminder.rule"].search([("active", "=", True)])
        if not default_rules:
            return

        contracts = self.search(
            [("state", "=", "active"), ("end_date", "!=", False)]
        )
        activity_type = self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)

        for contract in contracts:
            if not contract.end_date:
                continue
            days_to_end = (contract.end_date - today).days
            contract_rules = contract.reminder_rule_ids or default_rules
            for rule in contract_rules:
                if days_to_end != rule.days_before:
                    continue
                # Prevent duplicates with log table (SQL constraint also protects)
                existing = self.env["contract.reminder.sent"].sudo().search_count(
                    [
                        ("contract_id", "=", contract.id),
                        ("rule_id", "=", rule.id),
                        ("reminder_date", "=", today),
                    ]
                )
                if existing:
                    continue

                user = contract._get_reminder_user()
                summary = f"Vertrag endet in {rule.days_before} Tagen"
                note = f"Vertrag: {contract.name}"

                activity = False
                if activity_type:
                    activity = self.env["mail.activity"].sudo().create(
                        {
                            "activity_type_id": activity_type.id,
                            "summary": summary,
                            "note": note,
                            "date_deadline": today,
                            "res_model_id": self.env["ir.model"]._get_id("contract.contract"),
                            "res_id": contract.id,
                            "user_id": user.id,
                        }
                    )

                self.env["contract.reminder.sent"].sudo().create(
                    {
                        "contract_id": contract.id,
                        "rule_id": rule.id,
                        "reminder_date": today,
                        "activity_id": activity.id if activity else False,
                    }
                )
                self.env["contract.timeline"].sudo().create(
                    {
                        "contract_id": contract.id,
                        "event_type": "reminder",
                        "message": f"Erinnerung erstellt: {rule.days_before} Tage vor Ablauf",
                        "user_id": self.env.user.id,
                    }
                )

    def _cron_auto_set_expired(self):
        today = fields.Date.context_today(self)
        expired_contracts = self.search(
            [
                ("state", "in", ["active", "expiring"]),
                ("end_date", "!=", False),
                ("end_date", "<", today),
            ]
        )
        if expired_contracts:
            expired_contracts.write({"state": "expired"})

    def _cron_set_expiring(self):
        today = fields.Date.context_today(self)
        rules = self.env["contract.reminder.rule"].search([("active", "=", True)])
        if not rules:
            return
        threshold = min(rules.mapped("days_before"))

        expiring_contracts = self.search(
            [
                ("state", "=", "active"),
                ("end_date", "!=", False),
            ]
        )
        to_expiring = expiring_contracts.filtered(
            lambda c: c.end_date
            and 0 <= (c.end_date - today).days <= threshold
        )
        if to_expiring:
            to_expiring.write({"state": "expiring"})

    def _cron_auto_activate(self):
        today = fields.Date.context_today(self)
        to_activate = self.search(
            [
                ("state", "=", "draft"),
                ("approval_state", "=", "approved"),
                ("start_date", "!=", False),
                ("start_date", "<=", today),
            ]
        )
        if to_activate:
            to_activate.write({"state": "active"})

    def action_renew(self):
        for rec in self:
            if rec.end_date and rec.renewal_period_months and rec.renewal_period_months > 0:
                rec.end_date = fields.Date.add(rec.end_date, months=rec.renewal_period_months)
                rec.state = "active"
                self.env["contract.timeline"].create(
                    {
                        "contract_id": rec.id,
                        "event_type": "renew",
                        "message": "Vertrag manuell verlängert",
                        "user_id": self.env.user.id,
                    }
                )

    def _cron_auto_renew(self):
        today = fields.Date.context_today(self)
        to_renew = self.search(
            [
                ("auto_renew", "=", True),
                ("end_date", "!=", False),
                ("end_date", "<", today),
                ("state", "in", ["active", "expiring"]),
            ]
        )
        for rec in to_renew:
            if rec.renewal_period_months and rec.renewal_period_months > 0:
                new_end_date = rec.end_date
                while new_end_date and new_end_date < today:
                    new_end_date = fields.Date.add(
                        new_end_date, months=rec.renewal_period_months
                    )
                if not new_end_date:
                    continue
                previous_end_date = rec.end_date
                rec.end_date = new_end_date
                rec.state = "active"
                self.env["contract.timeline"].sudo().create(
                    {
                        "contract_id": rec.id,
                        "event_type": "renew",
                        "message": (
                            "Vertrag automatisch verlaengert: "
                            f"{previous_end_date} -> {new_end_date}"
                        ),
                        "user_id": self.env.user.id,
                    }
                )
