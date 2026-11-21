#!/bin/bash
# 2026-11-21: SEO fixes from the GSC review (commit fc3d432):
#  newest weekly page -> canonical to hub + out of sitemap; titles <=60 / descriptions <=155; country + bank links.
# Backup, smoke checks and auto-rollback are in deploy_files.py. Rollback by hand: restore the backup it prints.
set -e
cd /root/quantum-aether
python3 deploy/deploy_files.py --base fc3d432^ --tag seo-weekly-titles \
  --expect '/banks/weekly?lang=ar::arab-banks-2026-11/' \
  --expect '/adoption?lang=en::/adoption/countries/' \
  --expect '/deadlines?lang=ar::<title>مواعيد التشفير ما بعد الكمومي' \
  quantum_saas_app.py seo_meta.py weekly_banks.py weekly_insurers.py templates/base.html templates/adoption.html \
  templates/weekly_banks.html templates/weekly_insurers.html templates/_bank_report_links.html
W=$(curl -s https://ather-quantum.com/sitemap-pages.xml | grep -o '<loc>[^<]*weekly/2026-W[0-9]*' | sort -u | grep -c . || true)
echo "dated weekly URLs in sitemap (archives only): $W"
curl -s 'https://ather-quantum.com/banks/weekly/2026-W47?lang=ar' | grep -o '<link rel="canonical"[^>]*>'
git add deploy/seo_weekly_titles.sh && git commit -q -m "deploy: seo_weekly_titles.sh

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" || true
git fetch -q origin && git rebase -q origin/main && git push -q origin main && echo pushed
echo DONE
