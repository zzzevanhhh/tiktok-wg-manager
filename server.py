import json
import subprocess
import uuid
import secrets
from flask import Flask, request, render_template_string

app = Flask(__name__)
SINGBOX_CONF = '/etc/sing-box/config.json'

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>TikTok WG Manager</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background: #f0f2f5; padding: 20px; }
        .container { max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        h2 { color: #1a1a1a; }
        .form-group { margin-bottom: 15px; }
        label { display: block; margin-bottom: 5px; font-weight: bold; }
        input[type="number"], input[type="text"] { width: 100%; padding: 8px; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; }
        button { background: #10a37f; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; }
        button:hover { background: #0e906f; }
        .success { background: #d4edda; color: #155724; padding: 15px; border-radius: 4px; margin-top: 20px; word-break: break-all; }
    </style>
</head>
<body>
    <div class="container">
        <h2>🌐 极简 VLESS-WG 控制台</h2>
        <form method="POST">
            <div class="form-group">
                <label>监听端口 (如: 10001)</label>
                <input type="number" name="port" required>
            </div>
            <div class="form-group">
                <label>绑定的 WireGuard 网卡名 (如: wg_jp)</label>
                <input type="text" name="wg_interface" required placeholder="确保该网卡已在系统中启动">
            </div>
            <div class="form-group">
                <label>伪装域名 (SNI)</label>
                <input type="text" name="sni" value="www.microsoft.com" required>
            </div>
            <button type="submit">生成节点并重启服务</button>
        </form>
        {% if result %}
        <div class="success">
            <h3>✅ 节点创建成功！</h3>
            <p><b>UUID:</b> {{ result.uuid }}</p>
            <p><b>Public Key:</b> {{ result.pub_key }}</p>
            <p><b>Short ID:</b> {{ result.short_id }}</p>
            <p>请在软路由客户端填入以上信息，目标 IP 为本 VPS IP，端口为 {{ result.port }}。</p>
        </div>
        {% endif %}
    </div>
</body>
</html>
"""

def generate_reality_keys():
    try:
        res = subprocess.check_output(['sing-box', 'generate', 'reality-keypair'], text=True)
        lines = res.strip().split('\n')
        private_key = lines[0].split(': ')[1]
        public_key = lines[1].split(': ')[1]
        return private_key, public_key
    except Exception as e:
        return None, None

@app.route('/', methods=['GET', 'POST'])
def index():
    result = None
    if request.method == 'POST':
        port = int(request.form['port'])
        wg_interface = request.form['wg_interface']
        sni = request.form['sni']

        user_uuid = str(uuid.uuid4())
        short_id = secrets.token_hex(8)
        priv_key, pub_key = generate_reality_keys()

        if priv_key and pub_key:
            try:
                with open(SINGBOX_CONF, 'r') as f:
                    config = json.load(f)
                
                new_inbound = {
                    "type": "vless", "tag": f"in-{port}", "listen": "::", "listen_port": port,
                    "users": [{"uuid": user_uuid, "flow": "xtls-rprx-vision"}],
                    "tls": { "enabled": True, "server_name": sni, "reality": { "enabled": True, "handshake": { "server": sni, "server_port": 443 }, "private_key": priv_key, "short_id": [short_id] } }
                }
                
                new_outbound = { "type": "direct", "tag": f"out-{port}", "bind_interface": wg_interface }
                new_route = { "inbound": f"in-{port}", "outbound": f"out-{port}" }

                config['inbounds'].append(new_inbound)
                config['outbounds'].append(new_outbound)
                config['route']['rules'].insert(0, new_route)

                with open(SINGBOX_CONF, 'w') as f:
                    json.dump(config, f, indent=2)
                
                subprocess.run(['systemctl', 'restart', 'sing-box'])
                
                result = { 'uuid': user_uuid, 'pub_key': pub_key, 'short_id': short_id, 'port': port }
            except Exception as e:
                print(f"Error updating config: {e}")

    return render_template_string(HTML_TEMPLATE, result=result)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
