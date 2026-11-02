#!/usr/bin/env bash
# إعداد PayPal وكلمة مرور لوحة الإدارة. يُشغَّل بصلاحية root على الخادم:
#   bash /var/www/quantum_saas/deploy/configure.sh
# المدخلات السرية مخفية: لا تظهر على الشاشة ولا تدخل سجل الأوامر.
# يكتشف تلقائياً هل حساب PayPal في وضع live أم sandbox.
set -euo pipefail

ENV_FILE=/etc/quantum_saas.env
APP_DIR=/var/www/quantum_saas

[ "$(id -u)" -eq 0 ] || { echo "شغّل السكربت بصلاحية root" >&2; exit 1; }
[ -f "$ENV_FILE" ] || { echo "شغّل deploy/install.sh أولاً" >&2; exit 1; }

set -a
# shellcheck disable=SC1090
. "$ENV_FILE"
set +a

read -r -p "PayPal Client ID [${PAYPAL_CLIENT_ID:0:12}...] (Enter = بدون تغيير): " new_id
PAYPAL_CLIENT_ID="${new_id:-$PAYPAL_CLIENT_ID}"
read -r -s -p "PayPal Secret (Enter = بدون تغيير): " new_secret
echo
PAYPAL_CLIENT_SECRET="${new_secret:-$PAYPAL_CLIENT_SECRET}"

if [ -n "$PAYPAL_CLIENT_SECRET" ]; then
  detected=""
  for mode in live sandbox; do
    host=api-m.paypal.com
    [ "$mode" = sandbox ] && host=api-m.sandbox.paypal.com
    # السر يمر عبر stdin إلى curl، فلا يظهر في قائمة العمليات.
    code="$(printf 'user = "%s:%s"\n' "$PAYPAL_CLIENT_ID" "$PAYPAL_CLIENT_SECRET" \
      | curl -s -o /dev/null -w '%{http_code}' -K - -d grant_type=client_credentials "https://$host/v1/oauth2/token" || true)"
    if [ "$code" = 200 ]; then detected="$mode"; break; fi
  done
  if [ -z "$detected" ]; then
    echo "رفض PayPal المعرّف أو السر (live وsandbox). لم يتغير شيء." >&2
    exit 1
  fi
  PAYPAL_ENV="$detected"
  echo "PayPal: الحساب يعمل في وضع $PAYPAL_ENV"
fi

read -r -s -p "كلمة مرور لوحة الإدارة /admin (Enter = بدون تغيير): " admin_password
echo
if [ -n "$admin_password" ]; then
  QS_ADMIN_PASSWORD_HASH="$(printf '%s' "$admin_password" | "$APP_DIR/.venv/bin/python" -c \
    'import sys; from werkzeug.security import generate_password_hash; print(generate_password_hash(sys.stdin.read()))')"
fi

tmp="$(mktemp)"
chmod 600 "$tmp"
for key in QS_PUBLIC_URL QS_DATA_DIR QS_HASH_SALT QS_TRUSTED_PROXIES PAYPAL_CLIENT_ID PAYPAL_CLIENT_SECRET PAYPAL_ENV QS_ADMIN_PASSWORD_HASH; do
  printf "%s='%s'\n" "$key" "${!key:-}" >> "$tmp"
done
mv "$tmp" "$ENV_FILE"
chown root:root "$ENV_FILE"
chmod 600 "$ENV_FILE"

systemctl restart quantum_saas
for _ in $(seq 1 15); do
  curl -fsS http://127.0.0.1:8000/healthz && break
  sleep 1
done
echo
echo "تم. لوحة الإدارة: /admin (اسم المستخدم admin)"
