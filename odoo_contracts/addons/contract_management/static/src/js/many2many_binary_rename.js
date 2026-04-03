/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { Many2ManyBinaryField } from "@web/views/fields/many2many_binary/many2many_binary_field";

patch(Many2ManyBinaryField.prototype, {
    setup() {
        super.setup();
        this.action = useService("action");
    },

    async onFileUploaded(files) {
        let opened = false;
        for (const file of files) {
            if (file.error) {
                this.notification.add(file.error, {
                    title: _t("Uploading error"),
                    type: "danger",
                });
                continue;
            }
            await this.operations.saveRecord([file.id]);
            if (!opened && this._shouldPromptRename(file)) {
                opened = true;
                await this.action.doAction({
                    type: "ir.actions.act_window",
                    name: _t("Dateiname ändern"),
                    res_model: "contract.attachment.rename.wizard",
                    view_mode: "form",
                    views: [[false, "form"]],
                    target: "new",
                    context: { default_attachment_id: file.id },
                });
            }
        }
    },

    _shouldPromptRename(file) {
        return (
            this.props?.record?.resModel === "contract.contract" &&
            this.props?.name === "attachment_ids" &&
            file?.id
        );
    },
});
