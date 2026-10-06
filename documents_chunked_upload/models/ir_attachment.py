import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

PDF_INDEX_PARAM = 'documents_chunked_upload.pdf_index_max_mb'
PDF_INDEX_DEFAULT_MB = 5.0


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    @api.model
    def _index(self, bin_data, file_type, *args, **kwargs):
        """Skip full-text indexing of large PDFs.

        The ``attachment_indexation`` module extracts PDF text page by page
        with pdfminer in pure Python, which takes minutes on large technical
        drawings and blocks the upload request. Above the threshold the file
        is stored without a text index (it stays findable by name, folder
        and linked record). Set the parameter to 0 to skip all PDFs.
        """
        if file_type == 'application/pdf' and bin_data:
            try:
                limit_mb = float(
                    self.env['ir.config_parameter'].sudo().get_param(
                        PDF_INDEX_PARAM, PDF_INDEX_DEFAULT_MB)
                )
            except ValueError:
                limit_mb = PDF_INDEX_DEFAULT_MB
            if len(bin_data) > limit_mb * 1024 * 1024:
                _logger.info(
                    "Skipping PDF text indexing of %.1f MB attachment (limit %.1f MB)",
                    len(bin_data) / 1048576, limit_mb)
                return None
        return super()._index(bin_data, file_type, *args, **kwargs)
