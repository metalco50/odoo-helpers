from odoo import fields, models


class DocumentsUploadChunk(models.TransientModel):
    """One piece of a large file being uploaded in several requests.

    Transient: Odoo's autovacuum removes leftovers (failed or abandoned
    uploads). Pieces are also deleted right after the file is assembled.
    """
    _name = 'documents.upload.chunk'
    _description = 'Documents chunked upload piece'
    # abandoned pieces are vacuumed after this many hours
    _transient_max_hours = 12.0

    upload_id = fields.Char(required=True, index=True)
    user_id = fields.Many2one('res.users', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(required=True)
    # stored in the database column on purpose (not in the filestore) so
    # temporary pieces never interact with attachment hooks/offloading
    data = fields.Binary(attachment=False)
