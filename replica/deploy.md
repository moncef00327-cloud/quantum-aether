# Vultr publication
User explicitly authorized publishing the review design to Vultr. Existing domain, backend, payment configuration and data retained.
Preflight: 223 regression tests, 192 responsive checks, scanner fixture, drawer focus/Escape and production build passed.
Deploy command: python3 deploy/deploy_command.py
Deployment checks: production app integration, home HTML release marker, byte-exact public JS/CSS, business/pricing and LLM/OpenAPI endpoints.
Host: https://ather-quantum.com
Rollback: deployment script backs up every changed production file and rolls back automatically on failure.

Complete replacement release: 20261107-replace2. All service pages share the reference sidebar and CSS. Deployment removes all six obsolete interface assets and checks each returns HTTP 404. Backups include removed files for rollback.
