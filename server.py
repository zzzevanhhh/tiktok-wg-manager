cat << 'EOF' > /opt/tiktok-wg-manager/server.py
import json
import subprocess
import uuid
import secrets
import urllib.parse
from flask import Flask, request, render_template_string
import traceback
import os

app = Flask(__name__)
SINGBOX_CONF = '/etc/sing-box/config.json'

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>TikTok WG Manager v3.2</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background: #f0f2f5; padding: 20px; margin: 0; }
        .container { max-width: 900px; margin: 0 auto; background: white; padding: 30px; border-radius: 12px; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1); }
        h2 { color: #1a1a1a; margin-top: 0; border-bottom: 2px solid #e5e7eb; padding-bottom: 10px; }
        .panel { border: 1px solid #e5e7eb; border-radius: 8px; padding: 20px; margin-bottom: 25px; background: #fafafa; }
        .form-group { margin-bottom: 15px; }
        label { display: block; margin-bottom: 5px; font-weight: 600; color: #374151; font-size: 14px; }
        input[type="number"], input[type="text"] { width: 100%; padding: 10px; border: 1px solid #d1d5db; border-radius: 6px; box-sizing: border-box; }
        button { background: #10a37f; color: white; padding: 10px 20px; border: none; border-radius: 6px; cursor: pointer; font-weight: bold; }
        button.danger { background: #ef4444; }
        button:hover { opacity: 0.9; }
        .success { background: #ecfdf5; border: 1px solid #a7f3d0; color: #065f46; padding: 15px; border-radius: 8px; margin-bottom: 20px; }
        .error { background: #fef2f2; border: 1px solid #fecaca; color: #991b1b; padding: 15px; border-radius: 8px; margin-bottom: 20px; overflow-x: auto; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { text-align: left; padding: 12px; border-bottom: 1px solid #e5e7eb; }
        th { background: #f3f4f6; }
    </style>
</head>
<body>
    <div class="container">
        <h1 style="text-align: center; color: #111827;">🚀 跨境直播全局控制中心 v3.2</h1>
        
        {% if message %}<div class="success"><b>✅ 成功：</b>{{ message }}</div>{% endif %}
        {% if error %}<div class="error"><b>❌ 错误：</b><pre style="margin:0;">{{ error }}</pre></div>{% endif %}

        <div class="panel">
            <h2>🖥️ 已配置的 VLESS 节点列表</h2>
            {% if nodes %}
            <table>
                <tr><th>监听端口</th><th>伪装域名 (SNI)</th><th>绑定的 WG 网卡</th><th>操作</th></tr>
                {% for node in nodes %}
                <tr>
                    <td><b>{{ node.port }}</b></td>
                    <td>{{ node.sni }}</td>
                    <td><span style="background:#e0e7ff; color:#3730a3; padding:4px 8px; border-radius:4px; font-size:12px;">{{ node.wg }}</span></td>
                    <td>
                        <form method="POST" style="display:inline;">
                            <input type="hidden" name="action" value="del_vless">
                            <input type="hidden" name="port" value="{{ node.port }}">
                            <button type="submit" class="danger" style="padding: 6px 12px; font-size: 13px;" onclick="return confirm('确定要删除吗？')">删除</button>
                        </form>
                    </td>
                </tr>
                {% endfor %}
            </table>
            {% else %}
            <p style="color: #6b7280; font-size: 14px;">当前没有任何 VLESS 节点，请在下方创建。</p>
            {% endif %}
        </div>

        <div class="panel">
            <h2>第一步：添加底层 WireGuard 落地网卡</h2>
            <form method="POST">
                <input type="hidden" name="action" value="add_wg">
                <div style="display: flex; gap: 15px;">
                    <div class="form-group" style="flex: 1;">
                        <label>网卡名称 (如: wg_jp)</label>
                        <input type="text" name="wg_name" required>
                    </div>
                    <div class="form-group" style="flex: 1;">
                        <label>本地 IP (Address, 如: 10.66.66.2/32)</label>
                        <input type="text" name="address" required>
                    </div>
                </div>
                <div style="display: flex; gap: 15px;">
                    <div class="form-group" style="flex: 1;">
                        <label>节点私钥 (Private Key)</label>
                        <input type="text" name="private_key" required>
                    </div>
                    <div class="form-group" style="flex: 1;">
                        <label>节点公钥 (Peer Public Key)</label>
                        <input type="text" name="peer_pub" required>
                    </div>
                </div>
                <div class="form-group">
                    <label>服务端 Endpoint (填入NAT分给你的 IP:端口)</label>
                    <input type="text" name="endpoint" required>
                </div>
                <button type="submit">➕ 创建并启动 WG 网卡</button>
            </form>
        </div>

        <div class="panel">
            <h2>第二步：生成 VLESS 订阅</h2>
            <form method="POST">
                <input type="hidden" name="action" value="add_vless">
                <div style="display: flex; gap: 15px;">
                    <div class="form-group" style="flex: 1;">
                        <label>监听端口 (如: 10001)</label>
                        <input type="number" name="port" required>
                    </div>
                    <div class="form-group" style="flex: 1;">
                        <label>绑定的 WG 网卡名 (如: wg_jp)</label>
                        <input type="text" name="wg_interface" required>
                    </div>
                </div>
                <div style="display: flex; gap: 15px;">
                    <div class="form-group" style="flex: 1;">
                        <label>伪装域名 (SNI)</label>
                        <input type="text" name="sni" value="www.microsoft.com" required>
                    </div>
                    <div class="form-group" style="flex: 1;">
                        <label>本 VPS 公网 IP (用于生成订阅链接)</label>
                        <input type="text" name="vps_ip" value="{{ request.host.split(':')[0] }}" required>
                    </div>
                </div>
                <button type="submit">⚡ 自动生成节点并应用</button>
            </form>
        </div>
    </div>
</body>
</html>
"""

def load_config():
    if os.path.exists(SINGBOX_CONF) and os.path.getsize(SINGBOX_CONF) > 0:
        try:
            with open(SINGBOX_CONF, 'r') as f:
                return json.load(f)
        except: pass
    return {"log": {"level": "info"}, "inbounds": [], "outbounds": [{"type": "direct", "tag": "direct"}], "route": {"rules": [], "auto_detect_interface": True}}

def save_config(config):
    os.makedirs(os.path.dirname(SINGBOX_CONF), exist_ok=True)
    with open(SINGBOX_CONF, 'w') as f:
        json.dump(config, f, indent=2)

def get_nodes(config):
    nodes = []
    for inbound in config.get('inbounds', []):
        if inbound.get('type') == 'vless':
            port = inbound.get('listen_port')
            sni = inbound.get('tls', {}).get('server_name', 'N/A')
            wg_bind = "未知"
            for outbound in config.get('outbounds', []):
                if outbound.get('tag') == f"out-{port}":
                    wg_bind = outbound.get('bind_interface', 'direct')
            nodes.append({'port': port, 'sni': sni, 'wg': wg_bind})
    return nodes

@app.route('/', methods=['GET', 'POST'])
def index():
    message = None
    error = None
    config = load_config()

    if request.method == 'POST':
        action = request.form.get('action')
        try:
            if action == 'add_wg':
                wg_name = request.form['wg_name']
                wg_conf = f"""[Interface]
PrivateKey = {request.form['private_key']}
Address = {request.form['address']}
MTU = 1280
Table = off

[Peer]
PublicKey = {request.form['peer_pub']}
Endpoint = {request.form['endpoint']}
AllowedIPs = 0.0.0.0/0
PersistentKeepalive = 25
"""
                os.makedirs('/etc/wireguard', exist_ok=True)
                with open(f"/etc/wireguard/{wg_name}.conf", 'w') as f:
                    f.write(wg_conf)
                
                subprocess.run(['wg-quick', 'down', wg_name], capture_output=True)
                subprocess.run(['wg-quick', 'up', wg_name], capture_output=True)
                subprocess.run(['systemctl', 'enable', f'wg-quick@{wg_name}'])
                message = f"底层网卡 {wg_name} 已成功创建并启动！"

            elif action == 'add_vless':
                port = int(request.form['port'])
                wg_int = request.form['wg_interface']
                sni = request.form['sni']
                
                res = subprocess.check_output(['sing-box', 'generate', 'reality-keypair'], text=True)
                priv_key = res.strip().split('\n')[0].split(': ')[1]
                pub_key = res.strip().split('\n')[1].split(': ')[1]
                user_uuid = str(uuid.uuid4())
                short_id = secrets.token_hex(8)

                config['inbounds'].append({"type": "vless", "tag": f"in-{port}", "listen": "::", "listen_port": port, "users": [{"uuid": user_uuid, "flow": "xtls-rprx-vision"}], "tls": {"enabled": True, "server_name": sni, "reality": {"enabled": True, "handshake": {"server": sni, "server_port": 443}, "private_key": priv_key, "short_id": [short_id]}}})
                config['outbounds'].append({"type": "direct", "tag": f"out-{port}", "bind_interface": wg_int})
                config['route']['rules'].insert(0, {"inbound": f"in-{port}", "outbound": f"out-{port}"})
                
                save_config(config)
                subprocess.run(['systemctl', 'restart', 'sing-box'], check=True)
                
                qs = urllib.parse.urlencode({'encryption': 'none', 'flow': 'xtls-rprx-vision', 'security': 'reality', 'sni': sni, 'fp': 'chrome', 'pbk': pub_key, 'sid': short_id, 'type': 'tcp', 'headerType': 'none'})
                link = f"vless://{user_uuid}@{request.host.split(':')[0]}:{port}?{qs}#{wg_int}-{port}"
                message = f"节点生成成功！一键导入链接：\n{link}"

            elif action == 'del_vless':
                port = int(request.form['port'])
                config['inbounds'] = [i for i in config.get('inbounds', []) if i.get('listen_port') != port]
                config['outbounds'] = [o for o in config.get('outbounds', []) if o.get('tag') != f"out-{port}"]
                config['route']['rules'] = [r for r in config.get('route', {}).get('rules', []) if r.get('inbound'] != f"in-{port}"]
                save_config(config)
                subprocess.run(['systemctl', 'restart', 'sing-box'], check=True)
                message = f"端口 {port} 的节点已被成功删除！"

        except Exception as e:
            error = traceback.format_exc()

    nodes = get_nodes(config)
    return render_template_string(HTML_TEMPLATE, nodes=nodes, message=message, error=error)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
EOF

# 重启面板服务
systemctl restart wg-manager
systemctl restart sing-box
echo "✅ 经典轻量版已在本地强制生效并重启成功！"
