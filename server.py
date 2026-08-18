#!/bin/bash
echo "开始安装 Web 依赖与环境..."
apt update
apt install -y python3 python3-pip curl

echo "安装 Flask 框架..."
pip3 install Flask --break-system-packages

echo "创建管理目录并拉取核心代码..."
mkdir -p /opt/tiktok-wg-manager
cd /opt/tiktok-wg-manager
curl -o server.py -fsSL https://raw.githubusercontent.com/zzzevanhhh/tiktok-wg-manager/main/server.py

echo "配置 systemd 守护进程..."
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

echo "启动面板服务..."
systemctl daemon-reload
systemctl enable --now wg-manager

echo "✅ Web 面板部署完成！"
