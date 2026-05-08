#!/usr/bin/env bash
# Run once on a fresh Amazon Linux 2023 / Ubuntu t2.micro EC2 instance.
# Usage: bash ec2-setup.sh <AWS_REGION> <ECR_REGISTRY> <IMAGE_TAG>
set -euo pipefail

AWS_REGION=${1:-us-east-1}
ECR_REGISTRY=${2:?"\nUsage: ec2-setup.sh <AWS_REGION> <ECR_REGISTRY> <IMAGE_TAG>"}
IMAGE_TAG=${3:-latest}
IMAGE="${ECR_REGISTRY}/quantsentiment:${IMAGE_TAG}"

# ── Docker ────────────────────────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
    echo "[setup] Installing Docker..."
    sudo apt-get update -y
    sudo apt-get install -y docker.io
    sudo systemctl enable --now docker
    sudo usermod -aG docker "$USER"
fi

# ── AWS CLI ───────────────────────────────────────────────────────────────────
if ! command -v aws &>/dev/null; then
    echo "[setup] Installing AWS CLI..."
    sudo apt-get install -y awscli
fi

# ── nginx ─────────────────────────────────────────────────────────────────────
if ! command -v nginx &>/dev/null; then
    echo "[setup] Installing nginx..."
    sudo apt-get install -y nginx
fi

sudo cp "$(dirname "$0")/nginx.conf" /etc/nginx/sites-available/quantsentiment
sudo ln -sf /etc/nginx/sites-available/quantsentiment /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl enable --now nginx

# ── .env check ────────────────────────────────────────────────────────────────
ENV_FILE="/home/ubuntu/quantsentiment.env"
if [[ ! -f "$ENV_FILE" ]]; then
    echo "[setup] WARNING: $ENV_FILE not found."
    echo "        Copy your .env values there before the container starts."
    echo "        Example: scp .env ubuntu@<EC2_IP>:~/quantsentiment.env"
fi

# ── Pull & run container ──────────────────────────────────────────────────────
echo "[setup] Authenticating to ECR..."
aws ecr get-login-password --region "$AWS_REGION" \
    | sudo docker login --username AWS --password-stdin "$ECR_REGISTRY"

echo "[setup] Pulling $IMAGE..."
sudo docker pull "$IMAGE"

echo "[setup] Starting container..."
sudo docker stop quantsentiment 2>/dev/null || true
sudo docker rm   quantsentiment 2>/dev/null || true

sudo docker run -d \
    --name quantsentiment \
    --restart unless-stopped \
    -p 127.0.0.1:8000:8000 \
    --env-file "$ENV_FILE" \
    "$IMAGE"

sudo nginx -s reload
echo "[setup] Done. App running at http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)"
