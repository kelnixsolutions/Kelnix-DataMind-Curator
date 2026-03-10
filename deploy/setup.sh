#!/usr/bin/env bash
set -euo pipefail

# ── Kelnix DataMind Curator — first-time server setup ──────────────────
# Run on a fresh Ubuntu/Debian VPS (e.g. Hetzner)

APP_DIR="/opt/datamind-curator"
DOMAIN="datamind-api.kelnix.org"
REPO="https://github.com/kelnixsolutions/Kelnix-DataMind-Curator.git"

echo "=== Installing system dependencies ==="
apt-get update && apt-get install -y python3.12 python3.12-venv python3-pip git nginx certbot python3-certbot-nginx redis-server

echo "=== Cloning repository ==="
git clone "$REPO" "$APP_DIR" || (cd "$APP_DIR" && git pull)
cd "$APP_DIR"

echo "=== Creating virtual environment ==="
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "=== Setting up .env ==="
if [ ! -f .env ]; then
    cp .env.example .env
    echo "⚠️  Edit $APP_DIR/.env with your API keys before starting"
fi

echo "=== Creating service user ==="
id -u datamind &>/dev/null || useradd --system --no-create-home --shell /usr/sbin/nologin datamind
chown -R datamind:datamind "$APP_DIR"

echo "=== Creating systemd service ==="
cat > /etc/systemd/system/datamind.service << 'UNIT'
[Unit]
Description=Kelnix DataMind Curator API
After=network.target redis.service

[Service]
Type=simple
User=datamind
Group=datamind
WorkingDirectory=/opt/datamind-curator
EnvironmentFile=/opt/datamind-curator/.env
ExecStart=/opt/datamind-curator/.venv/bin/uvicorn app:app --host 0.0.0.0 --port 8001
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable datamind

echo "=== Configuring Nginx ==="
cat > /etc/nginx/sites-available/datamind << NGINX
server {
    server_name $DOMAIN;

    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 120s;
    }
}
NGINX

ln -sf /etc/nginx/sites-available/datamind /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx

echo "=== Setting up SSL ==="
certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --email admin@kelnix.org || echo "SSL setup requires DNS to point to this server first"

echo "=== Starting Redis ==="
systemctl enable redis-server
systemctl start redis-server

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Edit /opt/datamind-curator/.env with your API keys"
echo "  2. systemctl start datamind"
echo "  3. Check: curl https://$DOMAIN/health"
