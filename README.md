# GymVault - Gym Membership Management System

GymVault is a premium, full-stack Gym Membership Management System designed for efficiency, visual excellence, and AWS-powered cloud infrastructure. 

It features:
- **Member Management**: Complete CRUD operations, sequential Member IDs, membership expiry auto-calculations, and high-fidelity member photo handling.
- **Plan Management**: Fully customizable membership plans (duration, pricing, features list).
- **Payment Processing**: Receipt tracking, revenue statistics, payment breakdowns, and automated confirmation workflows.
- **Front-desk Check-ins**: Real-time validation of member status before allowing check-in, tracking attendance.
- **AWS Integration**: Leverages **S3** (secure photo storage), **KMS** (SSE-KMS encryption), **Secrets Manager** (connection strings and system config keys), and **SNS** (welcome notices, payment receipts, bulk expiry alerts).
- **Aesthetic Frontend**: Designed using vanilla HTML, CSS, and JS, featuring HSL-tailored dark/light accents, micro-animations, skeletons, glassmorphic design, and interactive modal dialogs.
- **Zero-Config Local Simulation**: Automatically falls back to local simulation modes (local filesystem photo storage, local logging of SNS notifications, and simulated KMS) when AWS credentials or services are unavailable, ensuring instant out-of-the-box local testing.

---

## Technical Stack & Architecture

### Backend
- **Core**: Python Flask REST API
- **Database**: MongoDB (runs on a separate server instance or locally)
- **WSGI / Web Server**: Gunicorn + Nginx (reverse proxy)
- **Deployment OS**: Ubuntu 22.04 LTS

### Frontend
- Single Page Application (SPA) built using pure HTML5, CSS3 Custom Properties, and Vanilla ES6+ JavaScript.
- Micro-interactions, modern font systems, icons, responsive sidebar, skeleton loaders, custom toasts, and confirmation drawers.

---

## Directory Structure

```
GymVault/
├── backend/
│   ├── routes/
│   │   ├── __init__.py      # Blueprint registration
│   │   ├── checkins.py      # Check-in API routes
│   │   ├── members.py       # Member CRUD and local photo serving
│   │   ├── payments.py      # Payment creation & statistics
│   │   └── plans.py         # Plan configuration CRUD
│   ├── app.py               # Flask Entrypoint and Health Checks
│   ├── config.py            # Local configurations and file validation
│   ├── database.py          # MongoDB connection and schema index creation
│   ├── kms_manager.py       # AWS KMS / Local simulated encryption manager
│   ├── s3_manager.py        # AWS S3 / Local filesystem storage manager
│   ├── secrets_manager.py   # AWS Secrets Manager / Local .env config manager
│   ├── sns_manager.py       # AWS SNS / Local simulated notification logger
│   └── requirements.txt     # Python packages list
├── frontend/
│   ├── app.js               # Main SPA JavaScript logic (AJAX/Fetch flow)
│   ├── index.html           # Shell HTML with layout wrappers
│   └── style.css            # Premium CSS Design System
├── .env.example             # Environment variable template
└── README.md                # Documentation
```

---

## Local Development Setup

### Prerequisite 1: MongoDB
1. Install MongoDB Community Server on your local system: [MongoDB Installation Guide](https://www.mongodb.com/docs/manual/administration/install-community/).
2. Start the MongoDB service. On Windows, it runs automatically as a system service. On macOS/Linux, run:
   ```bash
   mongod --dbpath <path-to-data-folder>
   ```

### Prerequisite 2: Python (Backend)
1. Navigate to the `backend` folder:
   ```bash
   cd backend
   ```
2. Create a virtual environment:
   ```bash
   python -m venv venv
   ```
3. Activate the virtual environment:
   - **Windows (cmd)**: `venv\Scripts\activate.bat`
   - **Windows (PowerShell)**: `venv\Scripts\Activate.ps1`
   - **macOS/Linux**: `source venv/bin/activate`
4. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
5. Create a `.env` file in the root of the project using the provided `.env.example` as a template.
6. Start the Flask development server:
   ```bash
   python app.py
   ```
   *The backend will run on `http://127.0.0.1:5000`.*

### Prerequisite 3: Frontend
Because the frontend is a Vanilla HTML/CSS/JS application:
1. You can open `frontend/index.html` directly in your browser.
2. Alternatively, serve it using any simple local server (e.g., Live Server extension in VS Code, or python's http module):
   ```bash
   # From the frontend directory
   python -m http.server 8000
   ```
   *The frontend will run on `http://127.0.0.1:8000`.*

---

## AWS Configuration & IAM Roles

To move from local simulation mode to AWS production mode, you must populate the keys in AWS Secrets Manager under the name `gymvault/config`. 

### Secrets Manager JSON Properties
Create a secret named `gymvault/config` in region `us-east-1` (or your chosen region) with the following key-value pairs:
```json
{
  "mongodb_uri": "mongodb://<DATABASE_EC2_PRIVATE_IP>:27017/gymvault",
  "mongodb_db_name": "gymvault",
  "s3_bucket_name": "gymvault-members-photos",
  "s3_region": "us-east-1",
  "kms_key_arn": "arn:aws:kms:us-east-1:123456789012:key/your-custom-kms-key-uuid",
  "sns_topic_arn": "arn:aws:sns:us-east-1:123456789012:gymvault-notifications",
  "gym_name": "GymVault Fitness Center",
  "gym_email": "admin@gymvault.com",
  "alert_days_before": "7"
}
```

### AWS IAM Policy for EC2 Instance Profile
Attach an IAM role to the App EC2 instance with the following policy to allow secure credential-free access:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "SecretsManagerAccess",
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue",
        "secretsmanager:DescribeSecret",
        "secretsmanager:ListSecrets"
      ],
      "Resource": "arn:aws:secretsmanager:us-east-1:123456789012:secret:gymvault/config-*"
    },
    {
      "Sid": "KMSAccess",
      "Effect": "Allow",
      "Action": [
        "kms:Decrypt",
        "kms:Encrypt",
        "kms:GenerateDataKey",
        "kms:DescribeKey",
        "kms:ListAliases"
      ],
      "Resource": "arn:aws:kms:us-east-1:123456789012:key/your-custom-kms-key-uuid"
    },
    {
      "Sid": "S3Access",
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject",
        "s3:ListBucket",
        "s3:HeadBucket"
      ],
      "Resource": [
        "arn:aws:s3:::gymvault-members-photos",
        "arn:aws:s3:::gymvault-members-photos/*"
      ]
    },
    {
      "Sid": "SNSAccess",
      "Effect": "Allow",
      "Action": [
        "sns:Publish",
        "sns:GetTopicAttributes"
      ],
      "Resource": "arn:aws:sns:us-east-1:123456789012:gymvault-notifications"
    }
  ]
}
```

---

## EC2 Deployment Guide (Ubuntu 22.04 LTS)

### Phase 1: Deploy Database Server (EC2 MongoDB Instance)
1. Launch an EC2 instance running Ubuntu 22.04 LTS for the database.
2. Install MongoDB:
   ```bash
   sudo apt update
   sudo apt install -y gnupg curl
   curl -fsSL https://www.mongodb.org/static/pgp/server-7.0.asc | sudo gpg --dearmor -o /usr/share/keyrings/mongodb-server-7.0.gpg
   echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg ] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-7.0.list
   sudo apt update
   sudo apt install -y mongodb-org
   ```
3. Configure MongoDB to listen on private network interface:
   Edit `/etc/mongod.conf` and change `bindIp` to `0.0.0.0` or `<private_ip_of_db_instance>`.
4. Start and enable MongoDB:
   ```bash
   sudo systemctl start mongod
   sudo systemctl enable mongod
   ```
5. Configure Security Group: Allow TCP port `27017` only from the private IP / Security Group of the Application EC2 instance.

### Phase 2: Deploy Application Server (EC2 App Instance)
1. Launch another Ubuntu 22.04 LTS EC2 instance. Attach the IAM role profile created earlier.
2. Update system and install packages:
   ```bash
   sudo apt update
   sudo apt upgrade -y
   sudo apt install -y python3-pip python3-venv nginx git
   ```
3. Clone project and setup virtual environment:
   ```bash
   git clone <your-github-repo-url> /var/www/gymvault
   cd /var/www/gymvault/backend
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
4. Set up systemd service configuration for Gunicorn:
   Create `/etc/systemd/system/gymvault.service`:
   ```ini
   [Unit]
   Description=GymVault Flask Service
   After=network.target

   [Service]
   User=www-data
   WorkingDirectory=/var/www/gymvault/backend
   Environment="PATH=/var/www/gymvault/backend/venv/bin"
   ExecStart=/var/www/gymvault/backend/venv/bin/gunicorn --workers 3 --bind 127.0.0.1:5000 app:app

   [Install]
   WantedBy=multi-user.target
   ```
5. Start and enable GymVault service:
   ```bash
   sudo systemctl start gymvault
   sudo systemctl enable gymvault
   ```

### Phase 3: Configure Nginx Reverse Proxy
1. Configure Nginx to serve the static frontend and proxy backend API calls.
2. Edit `/etc/nginx/sites-available/gymvault`:
   ```nginx
   server {
       listen 80;
       server_name yourdomain.com; # Or your EC2 public IP / DNS

       # Frontend Static Files
       location / {
           root /var/www/gymvault/frontend;
           index index.html;
           try_files $uri $uri/ =404;
       }

       # Backend API Proxy
       location /api {
           proxy_pass http://127.0.0.1:5000/api;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
           
           # Upload limit adjustments (allow image uploads up to 5MB)
           client_max_body_size 5M;
       }
   }
   ```
3. Enable configuration and restart Nginx:
   ```bash
   sudo ln -s /etc/nginx/sites-available/gymvault /etc/nginx/sites-enabled/
   sudo rm /etc/nginx/sites-enabled/default
   sudo nginx -t
   sudo systemctl restart nginx
   ```
4. Change file ownership:
   ```bash
   sudo chown -R www-data:www-data /var/www/gymvault
   ```
5. Configure Security Group: Allow TCP ports `80` (HTTP) and `443` (HTTPS) from the internet.

---

## API Documentation

### General / System
- **GET `/api/health`**
  Returns connectivity status, metrics, and configurations of system services.
- **POST `/api/aws/cache/clear`**
  Clears the in-memory Secrets Manager, S3, KMS, and SNS manager configuration caches.

### Members
- **GET `/api/members`**
  Fetches all members. Optional query params: `search` (name/email/id search), `status` (`Active`, `Expired`, `Expiring Soon`).
- **GET `/api/members/<member_id>`**
  Fetches a single member by sequential ID (e.g., `GYM001`).
- **POST `/api/members`**
  Creates a new member. Accepts `multipart/form-data` with member details and optional `photo` binary file.
- **PUT `/api/members/<member_id>`**
  Updates member text details and optional new profile photo upload.
- **DELETE `/api/members/<member_id>`**
  Deletes the member, associated check-in histories, and their encrypted photo.
- **PUT `/api/members/<member_id>/renew`**
  Renews a member subscription. Extends the membership end date based on selected plan duration, registers a payment transaction record, and emails a receipt.
- **GET `/api/members/photo/<path:filename>`**
  Serves member photos locally if the system is running in local fallback simulation mode.

### Plans
- **GET `/api/plans`**
  Lists all active membership packages.
- **POST `/api/plans`**
  Creates a new membership package.
- **PUT `/api/plans/<plan_id>`**
  Updates pricing, features, duration, and status of a plan.

### Payments
- **GET `/api/payments`**
  Lists all transactions. Optional query param: `member_id`.
- **POST `/api/payments`**
  Records an individual payment transaction.
- **GET `/api/payments/summary`**
  Calculates total revenue, monthly trends, payment mode share, and recent transactions.

### Check-ins
- **POST `/api/checkins`**
  Records a check-in. Validates membership end date. Denies entry if expired.
- **GET `/api/checkins/today`**
  Lists all check-ins for the current calendar date.
- **GET `/api/checkins/<member_id>`**
  Fetches up to 50 historical check-ins for a specific member.
