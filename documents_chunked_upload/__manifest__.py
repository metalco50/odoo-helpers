{
    'name': 'Documents Chunked Upload',
    'version': '19.0.1.0.3',
    'category': 'Productivity/Documents',
    'author': 'MFR Manufacturing Corp.',
    'maintainer': 'MFR Manufacturing Corp.',
    'summary': 'Upload large files to Documents in small pieces, below the hosting proxy limit',
    'description': """
AFTER INSTALLING YOU MUST SET THE PARAMETERS!
In developer mode go to Technical > Parameters > System Parameters and set
web.max_file_upload_size = 524288000 and document.max_fileupload_size = 524288000
(plain numbers only, no commas or units). See static/description/index.html or
README.md for the Shell alternative.

Large files (default: above 60 MB) are sent from the browser in 25 MB pieces
through /documents/upload_chunk, then assembled and stored by
/documents/upload_finish, which reuses the standard Documents upload logic.
Smaller files keep using the standard upload.
""",
    'depends': ['documents', 'attachment_indexation'],
    'data': [],
    'images': ['images/main_1.png', 'images/main_screenshot.png'],
    'assets': {
        'web.assets_backend': [
            'documents_chunked_upload/static/src/document_service_patch.js',
        ],
    },
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
}
