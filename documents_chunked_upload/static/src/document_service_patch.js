import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { DocumentService } from "@documents/core/document_service";

// Files above this size are sent in pieces. Files at or below it use the
// standard upload (a 90 MB single request is known to pass the proxy).
const CHUNK_THRESHOLD = 60 * 1024 * 1024;
const CHUNK_SIZE = 25 * 1024 * 1024;
const MAX_RETRIES = 3;

function newUploadId() {
    if (window.crypto && window.crypto.randomUUID) {
        return window.crypto.randomUUID().replaceAll("-", "");
    }
    let id = "";
    while (id.length < 32) {
        id += Math.random().toString(36).slice(2);
    }
    return id.slice(0, 32);
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

patch(DocumentService.prototype, {
    async uploadDocument(files, accessToken, context) {
        const fileArray = [...files];
        const small = fileArray.filter((file) => file.size <= CHUNK_THRESHOLD);
        const big = fileArray.filter((file) => file.size > CHUNK_THRESHOLD);
        if (small.length) {
            await super.uploadDocument(small, accessToken, context);
        }
        if (!big.length) {
            return;
        }
        // The size limit is enforced by the server in both chunk routes
        // (documents.document.get_document_max_upload_limit), so no
        // browser-side pre-check is done here.
        for (const file of big) {
            await this._uploadInChunks(file, accessToken, context);
        }
    },

    _chunkNotify(message, options = {}) {
        const notification =
            this.notification || (this.env && this.env.services && this.env.services.notification);
        if (notification) {
            return notification.add(message, options);
        }
        console.log(message);
        return () => {};
    },

    async _postChunk(uploadId, sequence, blob, totalSize) {
        let lastError;
        for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
            try {
                const formData = new FormData();
                formData.append("csrf_token", odoo.csrf_token);
                formData.append("upload_id", uploadId);
                formData.append("sequence", sequence);
                formData.append("total_size", totalSize);
                formData.append("chunk", blob, "chunk");
                const response = await fetch("/documents/upload_chunk", {
                    method: "POST",
                    body: formData,
                    credentials: "same-origin",
                });
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status} on piece ${sequence + 1}`);
                }
                return;
            } catch (error) {
                lastError = error;
                await sleep(1000 * attempt);
            }
        }
        throw lastError;
    },

    async _uploadInChunks(file, accessToken, context) {
        const uploadId = newUploadId();
        const totalChunks = Math.ceil(file.size / CHUNK_SIZE);
        let closeNotification = this._chunkNotify(
            _t("Uploading %(name)s: 0%", { name: file.name }),
            { sticky: true }
        );
        try {
            for (let i = 0; i < totalChunks; i++) {
                const blob = file.slice(i * CHUNK_SIZE, Math.min((i + 1) * CHUNK_SIZE, file.size));
                await this._postChunk(uploadId, i, blob, file.size);
                closeNotification();
                const percent = Math.round(((i + 1) / totalChunks) * 100);
                closeNotification = this._chunkNotify(
                    percent < 100
                        ? _t("Uploading %(name)s: %(percent)s%", { name: file.name, percent })
                        : _t("Processing %(name)s...", { name: file.name }),
                    { sticky: true }
                );
            }
        } catch (error) {
            closeNotification();
            this._chunkNotify(
                _t("Upload of %(name)s failed. Please try again.", { name: file.name }),
                { type: "danger" }
            );
            console.error("Chunked upload failed", error);
            return;
        }
        // Final request: standard upload service, so the view refreshes
        // exactly as after a normal upload. The placeholder file is empty;
        // the server assembles the real file from the stored pieces.
        const encodedToken = encodeURIComponent(accessToken || "");
        const placeholder = new File([], file.name, { type: file.type });
        try {
            await this.fileUpload.upload(`/documents/upload_finish/${encodedToken}`, [placeholder], {
                buildFormData: (formData) => {
                    formData.append("upload_id", uploadId);
                    formData.append("filename", file.name);
                    formData.append("mimetype", file.type || "");
                    formData.append("total_chunks", totalChunks);
                    formData.append("total_size", file.size);
                    if (context) {
                        for (const key of [
                            "default_user_folder_id",
                            "default_partner_id",
                            "default_res_id",
                            "default_res_model",
                        ]) {
                            if (context[key]) {
                                formData.append(key.replace("default_", ""), context[key]);
                            }
                        }
                        if (context.allowed_company_ids) {
                            formData.append(
                                "allowed_company_ids",
                                JSON.stringify(context.allowed_company_ids)
                            );
                        }
                        if (context.document_id) {
                            formData.append("document_id", context.document_id);
                        }
                    }
                },
                displayErrorNotification: false,
            });
        } finally {
            closeNotification();
        }
    },
});
