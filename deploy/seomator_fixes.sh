#!/bin/bash
# 2026-11-21: SEOmator audit fixes (commit db97b3e). Backup, smoke checks and auto-rollback are in deploy_files.py.
set -e
cd /root/quantum-aether
python3 deploy/deploy_files.py --base 8f384dc --tag seomator-fixes \
  --expect "/?lang=de::id=\"scanner\"" \
  --expect "/pricing?lang=en::/llms.txt\"" \
  --expect "/llms.txt::PQ-TLS Index (monthly" \
  --expect "/guides/enable-x25519mlkem768-nginx?lang=de::OpenSSL-Version prüfen" \
  quantum_saas_app.py guides.py pq_index.py exposure_web.py deadlines.py templates/base.html templates/pq_index.html \
  templates/exposure.html templates/command/en.html templates/command/ar.html templates/command_home.html \
  templates/index.html templates/monthly_report.html templates/llms.txt
