MochiAtlasDesigns design update

Upload app.py and requirements.txt to the repository root. Upload all files in static/ into the repository static/ directory. Keep existing other files unchanged.

Render build: pip install -r requirements.txt
Render start: gunicorn app:app

Routes: / storefront; /preview/studio, /preview/customer, /preview/notifications are PUBLIC DEMOS, NOT SECURE ADMIN/CUSTOMER PORTALS. Never enter real customer data or payment information in previews.

Existing /dashboard and /register are separate development Flask routes and are NOT production ready. Disable access to them before public launch. This design update is only a visual prototype.
