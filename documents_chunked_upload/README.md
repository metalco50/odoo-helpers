# Documents Chunked Upload

Upload large files to Odoo Documents in small pieces, without timeouts or proxy size errors.

## AFTER INSTALLING YOU MUST SET THE PARAMETERS!

Without this step, files above Odoo's default upload limit (64 MB) are refused.
Enter plain numbers only: no commas, spaces or units.

**Option 1: in the Odoo interface.** In developer mode go to
TECHNICAL > PARAMETERS > SYSTEM PARAMETERS.

- Search for `web.max_file_upload_size` and set it to `524288000` (recommended)
- Search for `document.max_fileupload_size` and set it to `524288000` (recommended)

**Option 2: in the Odoo Shell** (`odoo-bin shell`, or the Shell tab on Odoo.sh). Run one line at a time:

```python
env['ir.config_parameter'].sudo().set_param('web.max_file_upload_size', '524288000')
env['ir.config_parameter'].sudo().set_param('document.max_fileupload_size', '524288000')
env.cr.commit()
env.registry.clear_all_caches()
print(env['documents.document'].get_document_max_upload_limit())
```

The last line should print `524288000` (500 MB). Reload the page with Ctrl+Shift+R. If users still
see the old limit, save the same two parameters once in the interface, or restart the server.

## What it does

- Files above 60 MB are sent in 25 MB pieces and assembled on the server through the standard Documents upload.
- PDFs above 5 MB (system parameter `documents_chunked_upload.pdf_index_max_mb`) skip slow full-text indexing.
- Requires Odoo 19.0 with Documents (Enterprise) and `attachment_indexation`. Licensed LGPL-3.

See `static/description/index.html` for the full description, configuration table and limits.
