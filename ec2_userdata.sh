#!/usr/bin/env bash
# ==============================================================================
# GymVault EC2 Bootstrap Userdata Script (Ubuntu 22.04 LTS)
# Installs system dependencies, configures virtual environment,
# Gunicorn systemd daemon, and Nginx reverse proxy.
# ==============================================================================

# Exit on error
set -e

# Redirect outputs to log file for debugging
exec > >(tee -i /var/log/gymvault-setup.log) 2>&1

echo "=========================================================="
echo "⚡ Starting GymVault EC2 Bootstrap Setup..."
echo "=========================================================="

# 1. Update and install packages
echo "Updating apt cache and installing system packages..."
apt-get update
apt-get upgrade -y
apt-get install -y python3-pip python3-venv nginx git curl

# 2. Clone repository code
# REPLACE GITHUB_REPO_URL placeholder with your repository before launching
GITHUB_URL="https://github.com/Bharath-1602/GymVault.git"

if [ "$GITHUB_URL" = "GITHUB_REPO_URL" ] || [ -z "$GITHUB_URL" ]; then
    echo "⚠️ WARNING: GITHUB_REPO_URL not replaced! Defaulting to a placeholder directory."
    mkdir -p /var/www/gymvault
else
    echo "Cloning repository from $GITHUB_URL..."
    rm -rf /var/www/gymvault
    git clone "$GITHUB_URL" /var/www/gymvault
fi

# Make sure directory exists
mkdir -p /var/www/gymvault/backend
mkdir -p /var/www/gymvault/frontend

# 3. Setup python virtual environment and requirements
echo "Setting up Python virtual environment..."
cd /var/www/gymvault/backend
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
else
    echo "⚠️ requirements.txt not found! Installing base packages manually..."
    pip install flask flask-cors boto3 pymongo requests python-dotenv Pillow gunicorn
fi

# Create local uploads directory fallback
mkdir -p /var/www/gymvault/backend/uploads
chmod -R 775 /var/www/gymvault/backend/uploads

# 4. Create Gunicorn systemd unit file
echo "Creating Gunicorn systemd service file..."
cat <<EOF > /etc/systemd/system/gymvault.service
[Unit]
Description=GymVault Flask Service Daemon
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/gymvault/backend
Environment="PATH=/var/www/gymvault/backend/venv/bin"
ExecStart=/var/www/gymvault/backend/venv/bin/gunicorn --workers 3 --bind 127.0.0.1:5000 app:app

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd and start daemon
echo "Starting GymVault systemd service..."
systemctl daemon-reload
systemctl start gymvault
systemctl enable gymvault

# 5. Configure Nginx Reverse Proxy
echo "Creating Nginx configuration..."
cat <<EOF > /etc/nginx/sites-available/gymvault
server {
    listen 80;
    server_name _; # Responds to any public IP/Domain

    # Serving GymVault HTML/JS/CSS Frontend
    location / {
        root /var/www/gymvault/frontend;
        index index.html;
        try_files \$uri \$uri/ =404;
    }

    # Proxying API requests to Flask Backend
    location /api {
        proxy_pass http://127.0.0.1:5000/api;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;

        # Allow photo uploads up to 5MB
        client_max_body_size 5M;
    }
}
EOF

# Enable GymVault site configuration and disable default
echo "Activating Nginx site settings..."
ln -sf /etc/nginx/sites-available/gymvault /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Verify and restart Nginx
nginx -t
systemctl restart nginx

# 6. Setup correct directory permissions
echo "Adjusting file ownership permissions for www-data..."
chown -R www-data:www-data /var/www/gymvault
chmod -R 755 /var/www/gymvault

echo "=========================================================="
echo "🎉 GymVault EC2 Bootstrap Completed Successfully!"
echo "Check progress logs at /var/log/gymvault-setup.log"
echo "=========================================================="
