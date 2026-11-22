#!/bin/bash
# Growth agents (owner «نفذ الكل», 2026-11-22). Usage: bash deploy/growth.sh install|stop|start|status|uninstall
#   outreach  hourly 06:05-17:05 UTC, max 2 per run / 10 per day, published security.txt contacts only
#   leads     every 15 min: a reply from a contacted org -> owner email with a DRAFT (never auto-replies)
#   digest    daily 07:00 UTC to the owner
set -e
LIVE=/var/www/quantum_saas
DATA=/var/lib/quantum_saas
PY=$LIVE/.venv312/bin/python3
PAUSE=$DATA/growth.paused
case "${1:-status}" in
install)
  cd /root/quantum-aether
  [ -f $LIVE/growth_agent.py ] && cp -p $LIVE/growth_agent.py /root/backups/growth_agent.py.$(date -u +%Y%m%d%H%M%S)
  install -o root -g root -m 644 growth_agent.py $LIVE/growth_agent.py
  # history of every domain contacted by earlier batches (some logs live under /root, unreadable to the service)
  cat data/outreach_*sent*.json data/bounced_suppress.txt send_arab_batch*.py /root/outreach-*.csv 2>/dev/null \
    | grep -oiE '[a-z0-9.-]+\.[a-z]{2,}' | sort -u > $DATA/growth_history.txt
  chown quantum:quantum $DATA/growth_history.txt
  for job in outreach leads digest; do
    cat > /etc/systemd/system/quantum_growth_$job.service <<UNIT
[Unit]
Description=Quantum Aether growth agent: $job
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=quantum
Group=quantum
WorkingDirectory=$LIVE
EnvironmentFile=/etc/quantum_saas.env
Environment=PYTHONDONTWRITEBYTECODE=1
ExecStart=$PY growth_agent.py $job
TimeoutStartSec=1800
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=$DATA
UNIT
  done
  printf '[Unit]\nDescription=Growth outreach (hourly, working hours UTC)\n\n[Timer]\nOnCalendar=*-*-* 06..17:05:00 UTC\nPersistent=false\n\n[Install]\nWantedBy=timers.target\n' > /etc/systemd/system/quantum_growth_outreach.timer
  printf '[Unit]\nDescription=Growth leads check (every 15 min)\n\n[Timer]\nOnCalendar=*:0/15\n\n[Install]\nWantedBy=timers.target\n' > /etc/systemd/system/quantum_growth_leads.timer
  printf '[Unit]\nDescription=Growth daily digest (07:00 UTC)\n\n[Timer]\nOnCalendar=*-*-* 07:00:00 UTC\nPersistent=true\n\n[Install]\nWantedBy=timers.target\n' > /etc/systemd/system/quantum_growth_digest.timer
  systemctl daemon-reload
  systemctl enable --now quantum_growth_outreach.timer quantum_growth_leads.timer quantum_growth_digest.timer
  sudo -u quantum env $(grep -v '^#' /etc/quantum_saas.env | xargs -d '\n') $PY $LIVE/growth_agent.py status
  systemctl list-timers --no-pager | grep growth
  ;;
stop)  touch $PAUSE && chown quantum:quantum $PAUSE && echo "growth agents PAUSED (nothing will be sent)";;
start) rm -f $PAUSE && echo "growth agents RUNNING";;
status) [ -f $PAUSE ] && echo "PAUSED: $(cat $PAUSE)" || echo running; systemctl list-timers --no-pager | grep growth || true;;
uninstall)
  systemctl disable --now quantum_growth_outreach.timer quantum_growth_leads.timer quantum_growth_digest.timer || true
  rm -f /etc/systemd/system/quantum_growth_*.{service,timer}; systemctl daemon-reload; echo removed;;
esac
