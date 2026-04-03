import base64

from odoo import api, fields, models
from odoo.tools import html2plaintext
from odoo.exceptions import ValidationError
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
    department_id = fields.Many2one(
        "hr.department",
        string="Interne Abteilung",
        tracking=True,
    )
    start_date = fields.Date(string="Startdatum", tracking=True)
    end_date = fields.Date(string="Enddatum", tracking=True)
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


    def action_activate(self):
        self.write({"state": "active"})

    def action_cancel(self):
        self.write({"state": "cancelled"})

    def action_set_expired(self):
        self.write({"state": "expired"})

    def action_reset_draft(self):
        self.write({"state": "draft"})


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
        old_dates = {}
        old_misc = {}
        to_log = []
        if "state" in vals:
            for rec in self:
                old_states[rec.id] = rec.state
        if "start_date" in vals or "end_date" in vals:
            for rec in self:
                old_dates[rec.id] = (rec.start_date, rec.end_date)
        if "type_id" in vals or "partner_id" in vals or "responsible_user_id" in vals:
            for rec in self:
                old_misc[rec.id] = (rec.type_id, rec.partner_id, rec.responsible_user_id)
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
        if "type_id" in vals or "partner_id" in vals or "responsible_user_id" in vals:
            for rec in self:
                old_type, old_partner, old_resp = old_misc.get(rec.id, (False, False, False))
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
                rec.end_date = fields.Date.add(rec.end_date, months=rec.renewal_period_months)
                rec.state = "active"
                self.env["contract.timeline"].sudo().create(
                    {
                        "contract_id": rec.id,
                        "event_type": "renew",
                        "message": "Vertrag automatisch verlängert",
                        "user_id": self.env.user.id,
                    }
                )
