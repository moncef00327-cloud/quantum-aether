#!/bin/bash
# 2026-11-22: /bot page + /scanning public contact (backup/smoke/rollback in deploy_files.py), then growth agent
# reinstall (QuantumAetherBot UA; expand gets read access to the app log to find bots that name their site).
set -e
cd /root/quantum-aether
C=$(git log -1 --format=%h --grep='QuantumAetherBot identity')
python3 deploy/deploy_files.py --base "$C^" --tag bot-page \
  --expect '/bot?lang=en::QuantumAetherBot visited your site' --expect '/bot?lang=ar::زار QuantumAetherBot' \
  --expect '/scanning?lang=en::contact@mail.ather-quantum.com' \
  quantum_saas_app.py bot_page.py templates/bot.html templates/scanning.html
bash deploy/growth.sh install >/dev/null
grep -q SupplementaryGroups=systemd-journal /etc/systemd/system/quantum_growth_expand.service && echo "expand can read bot UAs"
git add deploy/bot_page.sh && git commit -q -m "deploy: bot_page.sh

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" || true
git fetch -q origin && git rebase -q origin/main && git push -q origin main && echo pushed
echo DONE
