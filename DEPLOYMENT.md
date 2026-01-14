# CryptoBot VPS Deployment Guide

## Prerequisites
- Ubuntu VPS with Docker & Docker Compose installed
- Nginx already running
- Git installed

---

## Step 1: Clone Repository

```bash
cd /opt  # or your preferred directory
git clone <your-repo-url> cryptobot
cd cryptobot
```

---

## Step 2: Configure Environment

```bash
cp .env.example .env
nano .env
```

Update these values:
```bash
# Database (use secure passwords in production!)
PG_USER=cryptobot_user
PG_PASSWORD=<strong-password>
PG_DB=cryptobot

# API Secret Key (generate with: openssl rand -hex 32)
SECRET_KEY=<random-32-char-string>

# Telegram Bot Token
TG_BOT_TOKEN=<your-telegram-token>

# Frontend URL (update when you have domain)
FRONTEND_URL=http://your-server-ip:3001
```

---

## Step 3: Start with Docker Compose

```bash
docker-compose up -d
```

Check if running:
```bash
docker-compose ps
docker-compose logs -f  # view logs
```

---

## Step 4: Configure Nginx Reverse Proxy

Create nginx config:
```bash
sudo nano /etc/nginx/sites-available/cryptobot
```

Add this configuration:
```nginx
# CryptoBot Frontend
server {
    listen 80;
    server_name cryptobot.yourdomain.com;  # or use server IP

    location / {
        proxy_pass http://localhost:3001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }
}

# CryptoBot API
server {
    listen 80;
    server_name api.cryptobot.yourdomain.com;  # or use different port

    location / {
        proxy_pass http://localhost:8001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;       # Important for WebSocket
        proxy_set_header Connection 'upgrade';        # Important for WebSocket
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        proxy_read_timeout 86400;                     # For WebSocket
    }
}
```

Enable and restart:
```bash
sudo ln -s /etc/nginx/sites-available/cryptobot /etc/nginx/sites-enabled/
sudo nginx -t  # test config
sudo systemctl reload nginx
```

---

## Step 5: Add SSL with Let's Encrypt (Optional but recommended)

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d cryptobot.yourdomain.com -d api.cryptobot.yourdomain.com
```

---

## Step 6: Update Frontend Environment

After setting up domain, update the frontend to use the correct API URL:

```bash
# In docker-compose.yml, update:
environment:
  - NEXT_PUBLIC_API_URL=https://api.cryptobot.yourdomain.com/api
  - NEXT_PUBLIC_WS_URL=wss://api.cryptobot.yourdomain.com
```

Rebuild frontend:
```bash
docker-compose up -d --build frontend
```

---

## Alternative: Access via IP Only (No Domain)

If no domain, use IP + ports:
- Frontend: `http://YOUR_VPS_IP:3001`
- API: `http://YOUR_VPS_IP:8001`

Update Nginx to proxy single domain with paths:
```nginx
server {
    listen 80;
    server_name YOUR_VPS_IP;

    # Frontend
    location / {
        proxy_pass http://localhost:3001;
        # ... proxy headers
    }

    # API
    location /api {
        proxy_pass http://localhost:8001/api;
        # ... proxy headers
    }

    # WebSocket
    location /ws {
        proxy_pass http://localhost:8001/ws;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
    }
}
```

---

## Useful Commands

```bash
# View logs
docker-compose logs -f api
docker-compose logs -f frontend

# Restart services
docker-compose restart

# Stop everything
docker-compose down

# Update and rebuild
git pull
docker-compose up -d --build
```

---

## Firewall (if using UFW)

```bash
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
# Only if accessing directly without nginx:
# sudo ufw allow 3001/tcp
# sudo ufw allow 8001/tcp
```
