import base64
import json
import logging
import re
import sys
import tempfile
import threading
import time
import traceback

from werkzeug.datastructures import FileStorage
from werkzeug.exceptions import BadRequest, Forbidden

from odoo import http
from odoo.http import request
from odoo.tools import replace_exceptions

from odoo.addons.documents.controllers.documents import ShareRoute

_logger = logging.getLogger(__name__)

UPLOAD_ID_RE = re.compile(r'^[A-Za-z0-9_-]{16,64}$')
MAX_CHUNKS = 4000
# One piece must stay far below the hosting proxy limit (a 90 MB request
# is known to pass, 128 MB is dropped). The browser sends 25 MB pieces.
MAX_CHUNK_REQUEST_SIZE = 64 << 20


class _StackSampler:
    """Diagnostic helper: while the wrapped block runs, log the current
    Python call stack of the request thread every ``interval`` seconds, so
    the log shows exactly which code is slow (Odoo, Documents, a connector...).
    """

    def __init__(self, label, interval=30.0):
        self.label = label
        self.interval = interval

    def __enter__(self):
        self._target = threading.get_ident()
        self._stop = threading.Event()
        self._t0 = time.monotonic()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def _run(self):
        while not self._stop.wait(self.interval):
            frame = sys._current_frames().get(self._target)
            if frame is None:
                continue
            stack = ''.join(traceback.format_stack(frame, limit=30))
            _logger.warning(
                "[chunked upload] %s still running after %.0fs. Current stack (innermost last):\n%s",
                self.label, time.monotonic() - self._t0, stack)

    def __exit__(self, *exc):
        self._stop.set()
        _logger.info("[chunked upload] %s took %.1fs", self.label, time.monotonic() - self._t0)
        return False


class DocumentsChunkedUpload(ShareRoute):

    @http.route('/documents/upload_chunk', type='http', auth='user',
                methods=['POST'], max_content_length=MAX_CHUNK_REQUEST_SIZE)
    def documents_upload_chunk(self, upload_id, sequence, total_size, chunk, **kw):
        """Store one piece of a large upload."""
        if not request.env.user._is_internal():
            raise Forbidden()
        if not UPLOAD_ID_RE.match(upload_id or ''):
            raise BadRequest("invalid upload id")
        with replace_exceptions(ValueError, by=BadRequest):
            sequence = int(sequence)
            total_size = int(total_size)
        if not 0 <= sequence < MAX_CHUNKS:
            raise BadRequest("invalid sequence")
        max_size = request.env['documents.document'].get_document_max_upload_limit()
        if total_size <= 0 or total_size > max_size:
            raise BadRequest("file exceeds the maximum upload size")

        files = request.httprequest.files.getlist('chunk')
        if len(files) != 1:
            raise BadRequest("exactly one piece is expected")
        raw = files[0].read()

        Chunk = request.env['documents.upload.chunk'].sudo()
        # a retried piece replaces the previous attempt
        Chunk.search([
            ('upload_id', '=', upload_id),
            ('user_id', '=', request.env.user.id),
            ('sequence', '=', sequence),
        ]).unlink()
        Chunk.create({
            'upload_id': upload_id,
            'user_id': request.env.user.id,
            'sequence': sequence,
            'data': base64.b64encode(raw),
        })
        return request.make_json_response({'ok': True, 'sequence': sequence})

    @http.route(['/documents/upload_finish/', '/documents/upload_finish/<access_token>'],
                type='http', auth='user', methods=['POST'],
                max_content_length=8 << 20)
    def documents_upload_finish(
        self,
        upload_id,
        filename,
        total_chunks,
        total_size,
        mimetype='',
        access_token='',
        user_folder_id='',
        owner_id='',
        partner_id='',
        res_id='',
        res_model=False,
        allowed_company_ids='',
        **kw
    ):
        """Assemble the stored pieces and create the document(s), using the
        standard ``_documents_upload`` logic (same permissions, folders,
        record linking and chatter note as a normal upload)."""
        user = request.env.user
        if not user._is_internal():
            raise Forbidden()
        if not UPLOAD_ID_RE.match(upload_id or ''):
            raise BadRequest("invalid upload id")
        if allowed_company_ids:
            request.update_context(allowed_company_ids=json.loads(allowed_company_ids))
        if access_token and user_folder_id or not access_token and user_folder_id not in {'COMPANY', 'MY'}:
            raise BadRequest("Incorrect token/user_folder_id values")

        # same target resolution and permission checks as documents_upload
        if not access_token:
            document_sudo = request.env['documents.document'].sudo()
        else:
            document_sudo = self._from_access_token(access_token)
            if (
                not document_sudo
                or (document_sudo.user_permission != 'edit'
                    and document_sudo.access_via_link != 'edit')
                or document_sudo.type not in ('binary', 'folder')
            ):
                raise request.not_found()

        with replace_exceptions(ValueError, by=BadRequest):
            owner_id = int(owner_id) if owner_id else user.id if not user_folder_id else None
            partner_id = int(partner_id) if partner_id else None
            res_id = int(res_id) if res_id else False
            total_chunks = int(total_chunks)
            total_size = int(total_size)
        if not 0 < total_chunks <= MAX_CHUNKS:
            raise BadRequest("invalid number of pieces")
        max_size = request.env['documents.document'].get_document_max_upload_limit()
        if total_size <= 0 or total_size > max_size:
            raise BadRequest("file exceeds the maximum upload size")

        Chunk = request.env['documents.upload.chunk'].sudo()
        chunks = Chunk.search(
            [('upload_id', '=', upload_id), ('user_id', '=', user.id)],
            order='sequence',
        )
        if [c.sequence for c in chunks] != list(range(total_chunks)):
            raise BadRequest("missing pieces, please retry the upload")

        tmp = tempfile.TemporaryFile()
        try:
            with _StackSampler(f"assemble {filename} ({total_size} bytes)"):
                written = 0
                for chunk in chunks:
                    raw = base64.b64decode(chunk.data or b'')
                    written += len(raw)
                    tmp.write(raw)
                    del raw
            if written != total_size:
                raise BadRequest("size mismatch, please retry the upload")
            tmp.seek(0)
            file = FileStorage(
                stream=tmp,
                filename=filename,
                content_type=mimetype or 'application/octet-stream',
            )
            with _StackSampler(f"create document for {filename}"):
                document_ids = self._documents_upload(
                    document_sudo, [file], owner_id, user_folder_id,
                    partner_id, res_id, res_model,
                )
        finally:
            tmp.close()
            chunks.unlink()
        return request.make_json_response(document_ids)
