#!/usr/bin/env bash
# تثبيت أو تحديث Quantum Aether على خادم Debian/Ubuntu. يُشغَّل بصلاحية root من نسخة المستودع:
#   bash deploy/install.sh
# يحافظ على البيانات (/var/lib/quantum_saas) والإعدادات (/etc/quantum_saas.env)،
# ويحفظ نسخة احتياطية من التثبيت السابق في /var/backups/quantum_saas.
set -euo pipefail

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR=/var/www/quantum_saas
DATA_DIR=/var/lib/quantum_saas
ENV_FILE=/etc/quantum_saas.env
BACKUP_DIR=/var/backups/quantum_saas
SERVICE=quantum_saas
APP_USER=quantum
PUBLIC_URL="${PUBLIC_URL:-https://ather-quatum.cloud}"
# معرّف PayPal العام الذي كان يستخدمه الموقع (ليس سراً؛ السر يُدخل عبر configure.sh).
DEFAULT_PAYPAL_CLIENT_ID="BAA9XULdxpQX54xlR5T2qj9mQyMRk8P0Tdn4KMBW98BruBpaAUwhOIG-l_29RhutQ_5Ec859jTd9lc4yL0"

[ "$(id -u)" -eq 0 ] || { echo "شغّل السكربت بصلاحية root" >&2; exit 1; }
[ "$SRC_DIR" != "$APP_DIR" ] || { echo "شغّل السكربت من نسخة المستودع وليس من $APP_DIR" >&2; exit 1; }

echo "==> الحزم"
if ! python3 -c "import ensurepip" >/dev/null 2>&1 || ! command -v rsync >/dev/null || ! command -v curl >/dev/null; then
  apt-get update -qq
  apt-get install -y -qq python3-venv rsync curl
fi

echo "==> المستخدم $APP_USER"
id -u "$APP_USER" >/dev/null 2>&1 || useradd --system --home-dir "$DATA_DIR" --shell /usr/sbin/nologin "$APP_USER"

echo "==> نسخة احتياطية"
STAMP="$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"
if [ -d "$APP_DIR" ]; then
  tar --exclude='.venv' -czf "$BACKUP_DIR/app-$STAMP.tar.gz" -C "$(dirname "$APP_DIR")" "$(basename "$APP_DIR")"
  echo "    $BACKUP_DIR/app-$STAMP.tar.gz"
fi

echo "==> البيانات"
install -d -o "$APP_USER" -g "$APP_USER" -m 750 "$DATA_DIR"
# سجل المبيعات القديم (CSV) يُحفظ للرجوع إليه؛ التطبيق الجديد يستخدم SQLite.
if [ -f "$APP_DIR/quantum_saas_sales.csv" ] && [ ! -f "$DATA_DIR/legacy_sales.csv" ]; then
  install -o "$APP_USER" -g "$APP_USER" -m 640 "$APP_DIR/quantum_saas_sales.csv" "$DATA_DIR/legacy_sales.csv"
fi

echo "==> الكود"
mkdir -p "$APP_DIR"
rsync -a --delete --exclude='.venv' --exclude='.git' --exclude='instance' --exclude='__pycache__' "$SRC_DIR/" "$APP_DIR/"
chown -R root:root "$APP_DIR"
chmod -R u=rwX,go=rX "$APP_DIR"

echo "==> البيئة الافتراضية"
if ! "$APP_DIR/.venv/bin/python" -c "import sys" >/dev/null 2>&1; then
  rm -rf "$APP_DIR/.venv"
  python3 -m venv "$APP_DIR/.venv"
fi
"$APP_DIR/.venv/bin/pip" install -q --upgrade pip
"$APP_DIR/.venv/bin/pip" install -q -r "$APP_DIR/requirements.txt"

echo "==> الإعدادات"
if [ ! -f "$ENV_FILE" ]; then
  SALT="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
  (
    umask 077
    cat > "$ENV_FILE" <<EOF
QS_PUBLIC_URL='$PUBLIC_URL'
QS_DATA_DIR='$DATA_DIR'
QS_HASH_SALT='$SALT'
QS_TRUSTED_PROXIES='1'
PAYPAL_CLIENT_ID='$DEFAULT_PAYPAL_CLIENT_ID'
PAYPAL_CLIENT_SECRET=''
PAYPAL_ENV='live'
QS_ADMIN_PASSWORD_HASH=''
EOF
  )
fi
chown root:root "$ENV_FILE"
chmod 600 "$ENV_FILE"

echo "==> systemd"
install -m 644 "$APP_DIR/deploy/quantum_saas.service" "/etc/systemd/system/$SERVICE.service"
systemctl daemon-reload
systemctl enable "$SERVICE" >/dev/null 2>&1
systemctl reset-failed "$SERVICE" >/dev/null 2>&1 || true
systemctl restart "$SERVICE"
# المهمة الأسبوعية لصفحة /adoption (تعيد فحص الأكبر 1000 وقوائم المراقبة كل يوم اثنين).
install -m 644 "$APP_DIR/deploy/quantum_adoption.service" /etc/systemd/system/quantum_adoption.service
install -m 644 "$APP_DIR/deploy/quantum_adoption.timer" /etc/systemd/system/quantum_adoption.timer
systemctl daemon-reload
systemctl enable --now quantum_adoption.timer >/dev/null 2>&1

echo "==> فحص الصحة"
healthy=""
for _ in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8000/healthz; then healthy=1; echo; break; fi
  sleep 1
done
if [ -z "$healthy" ]; then
  journalctl -u "$SERVICE" -n 40 --no-pager
  exit 1
fi

echo "==> nginx"
if command -v nginx >/dev/null; then
  # -R يتبع الروابط الرمزية في sites-enabled
  if ! grep -Rqs "127.0.0.1:8000" /etc/nginx/sites-enabled /etc/nginx/conf.d; then
    echo "تنبيه: لا يوجد proxy_pass إلى 127.0.0.1:8000 في إعدادات nginx؛ انظر deploy/nginx.conf.example" >&2
  fi
  nginx -t && systemctl reload nginx
fi

echo "تم التثبيت. لإعداد PayPal وكلمة مرور لوحة الإدارة: bash $APP_DIR/deploy/configure.sh"
