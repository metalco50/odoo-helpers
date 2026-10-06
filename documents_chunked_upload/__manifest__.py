{
    'name': 'Documents Chunked Upload',
    'version': '19.0.1.0.3',
    'category': 'Productivity/Documents',
    'summary': 'Upload large files to Documents in small pieces, below the hosting proxy limit',
    'description': """
Large files (default: above 60 MB) are sent from the browser in 25 MB pieces
through /documents/upload_chunk, then assembled and stored by
/documents/upload_finish, which reuses the standard Documents upload logic.
Smaller files keep using the standard upload.
""",
    'depends': ['documents', 'attachment_indexation'],
    'data': [],
    'assets': {
        'web.assets_backend': [
            'documents_chunked_upload/static/src/document_service_patch.js',
        ],
    },
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
}
