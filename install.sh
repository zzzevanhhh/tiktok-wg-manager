#!/bin/bash
echo "========================================"
echo "  TikTok 全局控制中心 - 终极安装脚本"
echo "========================================"

echo "[1/4] 更新系统并安装全部底层依赖 (WG, Python, Flask)..."
apt update
apt install -y wireguard openresolv python3-flask curl

echo "[2/4] 安装并配置 sing-box 核心环境..."
bash <(curl -fsSL https://sing-box.app/install.sh)

echo "[3/4] 拉取控制中心 Web 面板代码..."
mkdir -p /opt/tiktok-wg-manager
cd /opt/tiktok-wg-manager
# 注意：确认此处的 github 用户名是你的
curl -o server.py -fsSL https://raw.githubusercontent.com/zzzevanhhh/tiktok-wg-manager/main/server.py

echo "[4/4] 配置系统守护进程..."
cat > /etc/systemd/system/wg-manager.service <<EOF
[Unit]
Description=TikTok WG Manager Web UI
After=network.target

[Service]
User=root
WorkingDirectory=/opt/tiktok-wg-manager
ExecStart=/usr/bin/python3 /opt/tiktok-wg-manager/server.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now wg-manager
systemctl restart wg-manager

echo "========================================"
echo "✅ 所有组件及面板均已部署完成！"
echo "🌐 请在浏览器打开: http://$(curl -s ifconfig.me):5000"
echo "========================================"
