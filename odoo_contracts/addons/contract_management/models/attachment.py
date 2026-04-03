import base64
import io
import os
import re
import shutil
import subprocess
import tempfile

try:
    from PIL import Image
except Exception:  # pragma: no cover
    Image = None

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class IrAttachment(models.Model):
    _inherit = "ir.attachment"
    _order = "is_current desc, create_date desc"

    _ALLOWED_IMAGE_MIMETYPES = {
        "image/png",
        "image/jpeg",
        "image/jpg",
        "image/webp",
        "image/bmp",
        "image/tiff",
        "image/gif",
    }

    _ALLOWED_MIMETYPES = {"application/pdf"} | _ALLOWED_IMAGE_MIMETYPES

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
    ocr_extracted_at = fields.Datetime(string="OCR Zeitpunkt")
    ocr_text = fields.Text(string="OCR Text")

    version = fields.Integer(string="Version", default=0)
    is_current = fields.Boolean(string="Aktuell", default=False)
    version_label = fields.Char(string="Version (Anzeige)", compute="_compute_version_label", store=True)
    show_in_contract = fields.Boolean(string="In Vertrag anzeigen", default=False)

    internal_name = fields.Char(string="Interner Name")

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get("skip_contract_attachment"):
            return super().create(vals_list)
        for vals in vals_list:
            if vals.get("res_model") == "contract.contract" and vals.get("mimetype"):
                if vals.get("mimetype") not in self._ALLOWED_MIMETYPES:
                    raise ValidationError("Nur PDF- oder Bild-Dateien sind erlaubt.")
                if vals.get("mimetype") in self._ALLOWED_IMAGE_MIMETYPES:
                    if not vals.get("datas"):
                        raise ValidationError("Bilddaten fehlen. Bitte erneut hochladen.")
                    if Image is None:
                        raise ValidationError("Bildkonvertierung ist nicht verfügbar (Pillow fehlt).")
                    name = vals.get("name") or "upload"
                    pdf_name, pdf_datas = self._convert_image_to_pdf(name, vals.get("datas"))
                    vals["name"] = pdf_name
                    vals["datas"] = pdf_datas
                    vals["mimetype"] = "application/pdf"
        records = super().create(vals_list)
        for rec, vals in zip(records, vals_list):
            if rec.res_model == "contract.contract" and rec.res_id:
                if not rec.internal_name:
                    rec.internal_name = vals.get("internal_name") or vals.get("name") or rec.name
        for rec in records:
            if rec.res_model == "contract.contract" and rec.res_id:
                if not rec.version:
                    max_version = self.search(
                        [
                            ("res_model", "=", "contract.contract"),
                            ("res_id", "=", rec.res_id),
                        ],
                        order="version desc",
                        limit=1,
                    ).version or 0
                    rec.version = max_version + 1

                self.search(
                    [
                        ("res_model", "=", "contract.contract"),
                        ("res_id", "=", rec.res_id),
                        ("id", "!=", rec.id),
                        ("is_current", "=", True),
                    ]
                ).write({"is_current": False})
                rec.is_current = True

                if not rec.internal_name:
                    contract = self.env["contract.contract"].browse(rec.res_id)
                    timestamp = fields.Datetime.now().strftime("%Y%m%d_%H%M%S")
                    contract_number = contract.contract_number or "V-00000"
                    version_label = f"V{rec.version}" if rec.version else "V0"
                    rec.internal_name = f"{contract_number}_{timestamp}_{version_label}.pdf"

                # Only one visible attachment per contract (the latest)
                self.search(
                    [
                        ("res_model", "=", "contract.contract"),
                        ("res_id", "=", rec.res_id),
                        ("id", "!=", rec.id),
                        ("show_in_contract", "=", True),
                    ]
                ).write({"show_in_contract": False})
                rec.show_in_contract = True

                if rec.mimetype == "application/pdf":
                    rec.ocr_state = "pending"
                    self.env["contract.ocr.log"].create(
                        {
                            "attachment_id": rec.id,
                            "contract_id": rec.res_id,
                            "ocr_state": "pending",
                        }
                    )

                self.env["contract.timeline"].create(
                    {
                        "contract_id": rec.res_id,
                        "event_type": "attachment",
                        "message": f"Dokument hochgeladen: {rec.name}",
                        "user_id": self.env.user.id,
                    }
                )
        return records

    def _convert_image_to_pdf(self, name, datas_b64):
        decoded = base64.b64decode(datas_b64)
        image = Image.open(io.BytesIO(decoded))
        frames = []
        try:
            while True:
                frame = image.copy()
                if frame.mode in ("RGBA", "P", "LA"):
                    frame = frame.convert("RGB")
                frames.append(frame)
                image.seek(image.tell() + 1)
        except Exception:
            pass
        if not frames:
            frame = image.convert("RGB") if image.mode in ("RGBA", "P", "LA") else image
            frames = [frame]
        output = io.BytesIO()
        first, rest = frames[0], frames[1:]
        first.save(output, format="PDF", save_all=True, append_images=rest)
        pdf_bytes = output.getvalue()
        base, _dot, _ext = name.rpartition(".")
        if base:
            pdf_name = f"{base}.pdf"
        else:
            pdf_name = f"{name}.pdf"
        return pdf_name, base64.b64encode(pdf_bytes)

    def _get_ocr_languages(self):
        return (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("contract_management.ocr_languages", "deu+eng")
        )

    def _extract_text_with_ocrmypdf(self, pdf_bytes, languages):
        if not shutil.which("ocrmypdf"):
            return None, "ocrmypdf fehlt"
        with tempfile.TemporaryDirectory() as tmpdir:
            input_pdf = os.path.join(tmpdir, "input.pdf")
            output_pdf = os.path.join(tmpdir, "output.pdf")
            sidecar = os.path.join(tmpdir, "sidecar.txt")
            with open(input_pdf, "wb") as f:
                f.write(pdf_bytes)
            cmd = [
                "ocrmypdf",
                "--skip-text",
                "--redo-ocr",
                "--sidecar",
                sidecar,
                "-l",
                languages,
                input_pdf,
                output_pdf,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                err = result.stderr.strip() or f"ocrmypdf exit {result.returncode}"
                return "", err
            if not os.path.exists(sidecar):
                return "", None
            with open(sidecar, "r", encoding="utf-8", errors="ignore") as f:
                return f.read(), None

    def _strip_ocr_skipped_lines(self, text):
        if not text:
            return text
        lines = [
            line
            for line in text.splitlines()
            if not re.search(r"OCR skipped", line, flags=re.IGNORECASE)
        ]
        return "\n".join(lines).strip()

    def _extract_ocr_text(self, pdf_bytes, languages):
        text, err = self._extract_text_with_ocrmypdf(pdf_bytes, languages)
        if text is None:
            return None, err
        cleaned = self._strip_ocr_skipped_lines(text)
        return cleaned, err

    def cron_ocr_contract_attachments(self):
        log_model = self.env["contract.ocr.log"]
        attachments = self.search(
            [
                ("res_model", "=", "contract.contract"),
                ("mimetype", "=", "application/pdf"),
                ("ocr_state", "in", ["none", "pending", "error"]),
            ],
            limit=50,
        )
        languages = self._get_ocr_languages()
        for att in attachments:
            if not att.datas:
                att.write({"ocr_state": "error", "ocr_error": "Keine Datei-Daten."})
                log_model.create(
                    {
                        "attachment_id": att.id,
                        "contract_id": att.res_id,
                        "ocr_state": "error",
                        "ocr_error": "Keine Datei-Daten.",
                    }
                )
                continue
            pdf_bytes = base64.b64decode(att.datas)
            text, err = att._extract_ocr_text(pdf_bytes, languages)
            if text is None:
                error_msg = err or "OCR-Tools fehlen (ocrmypdf)."
                att.write({"ocr_state": "error", "ocr_error": error_msg})
                log_model.create(
                    {
                        "attachment_id": att.id,
                        "contract_id": att.res_id,
                        "ocr_state": "error",
                        "ocr_error": error_msg,
                    }
                )
                continue
            if err:
                att.write({"ocr_state": "error", "ocr_error": err})
                log_model.create(
                    {
                        "attachment_id": att.id,
                        "contract_id": att.res_id,
                        "ocr_state": "error",
                        "ocr_error": err,
                    }
                )
                continue
            att.write(
                {
                    "ocr_text": text or "",
                    "ocr_state": "done",
                    "ocr_error": False,
                    "ocr_extracted_at": fields.Datetime.now(),
                }
            )
            log_model.create(
                {
                    "attachment_id": att.id,
                    "contract_id": att.res_id,
                    "ocr_state": "done",
                    "ocr_text": text or "",
                }
            )

    def action_ocr_requeue(self):
        for rec in self:
            if rec.res_model != "contract.contract" or rec.mimetype != "application/pdf":
                continue
            rec.write({"ocr_state": "pending", "ocr_error": False})
            self.env["contract.ocr.log"].create(
                {
                    "attachment_id": rec.id,
                    "contract_id": rec.res_id,
                    "ocr_state": "pending",
                }
            )
        return True

    def write(self, vals):
        res = super().write(vals)
        if "show_in_contract" in vals:
            for rec in self:
                if rec.res_model != "contract.contract" or not rec.res_id:
                    continue
                if vals.get("show_in_contract"):
                    self.search(
                        [
                            ("res_model", "=", "contract.contract"),
                            ("res_id", "=", rec.res_id),
                            ("id", "!=", rec.id),
                            ("show_in_contract", "=", True),
                        ]
                    ).write({"show_in_contract": False})
        return res

    @api.depends("version")
    def _compute_version_label(self):
        for rec in self:
            rec.version_label = f"V{rec.version}" if rec.version else ""

    def action_download(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{self.id}",
            "target": "new",
        }

    def action_download_file(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{self.id}?download=true",
            "target": "self",
        }

    def action_rename_attachment(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Dateiname ändern",
            "res_model": "contract.attachment.rename.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_attachment_id": self.id},
        }

    def action_noop(self):
        return False
