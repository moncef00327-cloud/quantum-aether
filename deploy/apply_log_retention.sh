#!/bin/bash
# 2026-11-21: make the privacy policy true, THEN publish it.
#  1) journald keeps at most 14 days (drop-in), older entries are vacuumed now
#  2) old nginx logs (nginx stopped since 2026-11-03, so logrotate no longer touches them) older than 14 days are deleted
#  3) legal.py (/datenschutz: 14-day log retention + Resend SCC basis) is committed, deployed with backup/smoke checks, pushed
# The Vultr DPA clause stays a visible placeholder until the owner confirms it.
set -e
echo "== 1) journald retention 14 days"
mkdir -p /etc/systemd/journald.conf.d
printf '[Journal]\n# privacy policy (/datenschutz): server logs are deleted after at most 14 days\nMaxRetentionSec=14day\n' \
  > /etc/systemd/journald.conf.d/retention.conf
systemctl restart systemd-journald
journalctl --vacuum-time=14d 2>&1 | tail -1
journalctl --disk-usage
echo "== 2) nginx logs older than 14 days"
find /var/log/nginx -type f -mtime +13 -print -delete

echo "== 3) publish /datenschutz"
cd /root/quantum-aether
if ! git log -1 --format=%s | grep -q "14-day log retention"; then
  git add -- legal.py deploy/apply_log_retention.sh
  git commit -q -m "legal(datenschutz): 14-day log retention (enforced by journald) + Resend SCC transfer basis

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
fi
python3 deploy/deploy_files.py --base "$(git rev-parse HEAD^)" --tag datenschutz \
  --expect '/datenschutz?lang=en::14 days' --expect '/datenschutz?lang=de::14 Tagen' legal.py
git fetch -q origin && git rebase -q origin/main && git push -q origin main && echo pushed
echo "DONE"
