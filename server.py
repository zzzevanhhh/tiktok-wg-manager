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
    <title>TikTok WG Manager v2</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background: #f0f2f5; padding: 20px; margin: 0; }
        .container { max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 12px; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1); }
        h2 { color: #1a1a1a; margin-top: 0; text-align: center; }
        .form-group { margin-bottom: 20px; }
        label { display: block; margin-bottom: 8px; font-weight: 600; color: #374151; }
        input[type="number"], input[type="text"] { width: 100%; padding: 12px; border: 1px solid #d1d5db; border-radius: 6px; box-sizing: border-box; font-size: 16px; }
        button { background: #10a37f; color: white; padding: 14px 20px; border: none; border-radius: 6px; cursor: pointer; font-size: 16px; width: 100%; font-weight: bold; transition: background 0.2s; }
        button:hover { background: #0e906f; }
        .success { background: #ecfdf5; border: 1px solid #a7f3d0; color: #065f46; padding: 20px; border-radius: 8px; margin-top: 25px; }
        .error { background: #fef2f2; border: 1px solid #fecaca; color: #991b1b; padding: 20px; border-radius: 8px; margin-top: 25px; overflow-x: auto; }
        .vless-link { background: #f3f4f6; padding: 15px; border-radius: 6px; font-family: monospace; font-size: 14px; margin-top: 15px; word-break: break-all; border: 1px dashed #9ca3af; }
    </style>
</head>
<body>
    <div class="container">
        <h2>🚀 VLESS ➔ WG 极简控制台 v2.0</h2>
        <form method="POST">
            <div class="form-group">
                <label>监听端口 (如: 10001)</label>
                <input type="number" name="port" required placeholder="输入一个未被占用的端口">
            </div>
            <div class="form-group">
                <label>绑定的 WireGuard 网卡名 (如: wg_jp)</label>
                <input type="text" name="wg_interface" required placeholder="例如 wg_hk 或 wg_jp">
            </div>
            <div class="form-group">
                <label>伪装域名 (SNI)</label>
                <input type="text" name="sni" value="www.microsoft.com" required>
            </div>
            <div class="form-group">
                <label>本 VPS 公网 IP (用于生成订阅链接)</label>
                <input type="text" name="vps_ip" value="{{ request.host.split(':')[0] }}" required>
            </div>
            <button type="submit">⚡ 自动生成节点并应用</button>
        </form>
        
        {% if error %}
        <div class="error">
            <h3 style="margin-top:0;">❌ 发生错误！</h3>
            <pre style="margin:0;">{{ error }}</pre>
        </div>
        {% endif %}

        {% if result %}
        <div class="success">
            <h3 style="margin-top:0;">✅ 节点创建成功并已重启生效！</h3>
            <p><b>一键导入链接 (复制后打开 V2rayNG/Shadowrocket/Passwall 导入):</b></p>
            <div class="vless-link">{{ result.vless_link }}</div>
            <p style="font-size:13px; color:#6b7280; margin-bottom:0;">提示：测试通顺后，将链接导入 Kwrt 的节点列表即可使用。</p>
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
        raise Exception(f"生成 Reality 密钥对失败，请确保 sing-box 已正确安装: {str(e)}")

@app.route('/', methods=['GET', 'POST'])
def index():
    result = None
    error = None
    if request.method == 'POST':
        try:
            port = int(request.form['port'])
            wg_interface = request.form['wg_interface']
            sni = request.form['sni']
            vps_ip = request.form['vps_ip']

            user_uuid = str(uuid.uuid4())
            short_id = secrets.token_hex(8)
            priv_key, pub_key = generate_reality_keys()

            # 读取配置或初始化全新配置
            config = {}
            if os.path.exists(SINGBOX_CONF) and os.path.getsize(SINGBOX_CONF) > 0:
                try:
                    with open(SINGBOX_CONF, 'r') as f:
                        config = json.load(f)
                except json.decoder.JSONDecodeError:
                    raise Exception(f"配置文件 {SINGBOX_CONF} 格式损坏，请手动清理或删除它。")
            else:
                # 给新机器初始化骨架
                os.makedirs(os.path.dirname(SINGBOX_CONF), exist_ok=True)
                config = {
                    "log": {"level": "info", "timestamp": True},
                    "inbounds": [],
                    "outbounds": [{"type": "direct", "tag": "direct"}],
                    "route": {"rules": [], "auto_detect_interface": True}
                }

            # 确保节点不丢失
            if 'inbounds' not in config: config['inbounds'] = []
            if 'outbounds' not in config: config['outbounds'] = []
            if 'route' not in config: config['route'] = {"rules": []}
            if 'rules' not in config['route']: config['route']['rules'] = []

            # 构建节点代碼
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

            # 写回配置文件
            with open(SINGBOX_CONF, 'w') as f:
                json.dump(config, f, indent=2)
            
            # 重新启动 sing-box
            subprocess.run(['systemctl', 'restart', 'sing-box'], check=True)
            
            # 生成标准 vless:// 订阅链接
            query_params = {
                'encryption': 'none',
                'flow': 'xtls-rprx-vision',
                'security': 'reality',
                'sni': sni,
                'fp': 'chrome',
                'pbk': pub_key,
                'sid': short_id,
                'type': 'tcp',
                'headerType': 'none'
            }
            query_string = urllib.parse.urlencode(query_params)
            node_name = urllib.parse.quote(f"TikTok-{wg_interface}-{port}")
            vless_link = f"vless://{user_uuid}@{vps_ip}:{port}?{query_string}#{node_name}"

            result = { 'vless_link': vless_link }

        except Exception as e:
            error = traceback.format_exc()

    return render_template_string(HTML_TEMPLATE, result=result, error=error)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
