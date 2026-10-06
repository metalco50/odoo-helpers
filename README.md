# odoo-helpers
Odoo Utilities and Work Arounds
Purpose and status
The module lets Documents accept files far larger than Odoo.sh will pass in one request,
and keeps large PDFs from stalling on text indexing. It is version 19.0.1.0.3 and runs in
production, verified with a 90 MB PDF on 2026-10-05.
Two problems drove it:
Platform request cap. A single 90 MB upload request passed, but a 128 MB request
was dropped by the Odoo.sh proxy before Odoo saw it (browser error
ERR_HTTP2_PROTOCOL_ERROR , no matching line in odoo.log ). The cap sits somewhere
between those two sizes. It is observed, not documented, and raising Odoo's own
limits cannot change it.
Slow PDF processing. The standard attachment_indexation add-on reads every PDF
page with pdfminer in pure Python to build a search index. For a 90 MB drawing, the
final upload step spent 377 s in Python and about 1 s in the database.
The module works inside Odoo.sh and needs nothing on your office network or NAS.
