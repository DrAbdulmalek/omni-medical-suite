#!/bin/bash
# =============================================================================
# Omni Medical Suite — SSL Certificate Setup Helper
# =============================================================================
# Standalone script for setting up or renewing SSL
# Usage: ./setup-ssl.sh --domain your-domain.com --email admin@your-domain.com
# =============================================================================

set -euo pipefail

DOMAIN=""
EMAIL=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --domain) DOMAIN="$2"; shift 2 ;;
        --email)  EMAIL="$2";  shift 2 ;;
        *) echo "Unknown: $1"; exit 1 ;;
    esac
done

[[ -z "$DOMAIN" ]] && { echo "Error: --domain required"; exit 1; }
[[ -z "$EMAIL" ]]  && { echo "Error: --email required"; exit 1; }

echo "=== SSL Setup for $DOMAIN ==="

# Install certbot if needed
command -v certbot &>/dev/null || apt install -y certbot python3-certbot-nginx

# Create webroot
mkdir -p /var/www/certbot

# Get certificate
echo "Requesting certificate..."
certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    -d "$DOMAIN" \
    --email "$EMAIL" \
    --agree-tos \
    --non-interactive

# Generate DH params
if [[ ! -f /etc/nginx/dhparam.pem ]]; then
    echo "Generating DH parameters (2048-bit)..."
    openssl dhparam -out /etc/nginx/dhparam.pem 2048
fi

# Update Nginx config with real cert paths
NGINX_CONF="/etc/nginx/sites-available/omni-medical.conf"
if [[ -f "$NGINX_CONF" ]]; then
    sed -i "s|ssl_certificate .*;|ssl_certificate /etc/letsencrypt/live/${DOMAIN}/fullchain.pem;|g" "$NGINX_CONF"
    sed -i "s|ssl_certificate_key .*;|ssl_certificate_key /etc/letsencrypt/live/${DOMAIN}/privkey.pem;|g" "$NGINX_CONF"
fi

# Test and reload
nginx -t && systemctl reload nginx

# Auto-renewal cron
(crontab -l 2>/dev/null; echo "0 3 * * * certbot renew --quiet --deploy-hook 'systemctl reload nginx'") | sort -u | crontab -

echo "=== SSL Setup Complete ==="
echo "  Certificate: /etc/letsencrypt/live/${DOMAIN}/fullchain.pem"
echo "  Auto-renewal: Daily at 3:00 AM"
