#!/bin/bash
# 2026-11-21: short answer + FAQ on the 6 guides that rank in Google (commit below). Backup/smoke/rollback in deploy_files.py.
set -e
cd /root/quantum-aether
C=$(git log -1 --format=%h --grep='short answer under H1 + FAQ')
python3 deploy/deploy_files.py --base "$C^" --tag guide-faq \
  --expect '/guides/enable-x25519mlkem768-nginx?lang=en::id="short-answer"' \
  --expect '/guides/enable-x25519mlkem768-nginx?lang=de::Häufige Fragen' \
  --expect '/guides/gulf-banks-post-quantum-cryptography-requirements?lang=ar::"FAQPage"' \
  --expect '/guides/go-post-quantum-tls-x25519mlkem768?lang=en::RFC 10024' \
  quantum_saas_app.py guide_faq.py guides.py templates/guide.html
git add deploy/guide_faq.sh && git commit -q -m "deploy: guide_faq.sh

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" || true
git fetch -q origin && git rebase -q origin/main && git push -q origin main && echo pushed
echo DONE
