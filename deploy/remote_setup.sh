#!/usr/bin/env bash
# anbu-api 원격 배포 스크립트 (Ubuntu 22.04, 서버에서 실행).
# 코드 전송(rsync) 이후 실행된다.
# 필요한 환경변수: SUDO_PW(sudo 비밀번호), ANBU_ADMIN_PW(대시보드 admin 비밀번호)
set -euo pipefail

APP_DIR=/home/inno-hi/anbu-api
IP=1.214.89.64
: "${SUDO_PW:?SUDO_PW 환경변수가 필요합니다(sudo 비밀번호)}"
: "${ANBU_ADMIN_PW:?ANBU_ADMIN_PW 환경변수가 필요합니다(대시보드 admin 초기 비밀번호)}"
ADMIN_PW="${ANBU_ADMIN_PW}"

sudo_do() { echo "$SUDO_PW" | sudo -S -p '' "$@"; }

echo "### 1. 시스템 패키지 설치"
sudo_do apt-get update -qq
sudo_do DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
    python3-venv python3-pip nginx openssl >/dev/null

echo "### 2. 가상환경 + 의존성"
cd "$APP_DIR"
python3 -m venv .venv
./.venv/bin/pip install -q --upgrade pip
./.venv/bin/pip install -q -r requirements.txt
./.venv/bin/pip install -q -e . --no-deps

echo "### 3. .env 생성(비밀키 무작위) — 이미 있으면 유지"
if [ ! -f .env ]; then
  PSK=$(openssl rand -hex 32)
  JWT=$(openssl rand -hex 32)
  FERNET=$(./.venv/bin/python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())")
  cat > .env <<EOF
ACCUM_DB_URL=sqlite:///data/accum.db
TRANSFER_DB_URL=sqlite:///data/transfer.db
OPS_DB_URL=sqlite:///data/ops.db
PSEUDONYM_SECRET_KEY=${PSK}
MAPPING_ENCRYPTION_KEY=${FERNET}
JWT_SECRET_KEY=${JWT}
JWT_EXPIRE_MINUTES=60
MQTT_HOST=127.0.0.1
MQTT_PORT=1883
MQTT_TOPIC_PREFIX=anbu
TZ=Asia/Seoul
EOF
  echo ".env 생성 완료"
else
  echo ".env 기존 파일 유지"
fi

echo "### 4. DB 초기화 + 관리자 계정 + 데모 데이터(최초 1회)"
set -a; . ./.env; set +a
if [ ! -f data/ops.db ]; then
  ./.venv/bin/python -m anbu_api.cli init-db
  ./.venv/bin/python -m anbu_api.cli seed --subjects 6 --days 2
  ./.venv/bin/python -m anbu_api.cli etl intervals
  ./.venv/bin/python -m anbu_api.cli etl status
  ./.venv/bin/python -m anbu_api.cli etl inactivity
  ./.venv/bin/python -m anbu_api.cli pseudo-run
  ./.venv/bin/python -m anbu_api.cli publish --dry-run
  ./.venv/bin/python -m anbu_api.cli create-user --username admin --role super_admin --password "$ADMIN_PW"
  echo "관리자 계정 생성: admin"
else
  echo "data/ 기존 DB 유지(초기화 건너뜀)"
fi

echo "### 5. systemd 서비스 등록"
sudo_do cp deploy/anbu-api.service /etc/systemd/system/anbu-api.service
sudo_do systemctl daemon-reload
sudo_do systemctl enable --now anbu-api
sleep 2
sudo_do systemctl --no-pager --full status anbu-api | head -6 || true

echo "### 6. self-signed TLS 인증서(IP SAN)"
sudo_do mkdir -p /etc/nginx/ssl
if ! sudo_do test -f /etc/nginx/ssl/anbu.crt; then
  sudo_do openssl req -x509 -newkey rsa:2048 -nodes \
    -keyout /etc/nginx/ssl/anbu.key -out /etc/nginx/ssl/anbu.crt -days 825 \
    -subj "/C=KR/O=Dongguk COSS/CN=${IP}" -addext "subjectAltName=IP:${IP}" >/dev/null 2>&1
  echo "인증서 생성 완료"
else
  echo "인증서 기존 파일 유지"
fi

echo "### 7. nginx 사이트 구성"
sudo_do cp deploy/nginx-anbu.conf /etc/nginx/sites-available/anbu
sudo_do ln -sf /etc/nginx/sites-available/anbu /etc/nginx/sites-enabled/anbu
sudo_do rm -f /etc/nginx/sites-enabled/default
sudo_do nginx -t
sudo_do systemctl reload nginx

echo "### 8. 방화벽(ufw 활성 시 443/80 허용)"
if sudo_do ufw status 2>/dev/null | grep -q "Status: active"; then
  sudo_do ufw allow 80/tcp >/dev/null
  sudo_do ufw allow 443/tcp >/dev/null
  echo "ufw 80/443 허용"
else
  echo "ufw 비활성 — 건너뜀"
fi

echo "### 9. 로컬 검증"
curl -sk -o /dev/null -w "https 로컬 응답: %{http_code}\n" https://127.0.0.1/dashboard || true
echo "### 배포 완료"
