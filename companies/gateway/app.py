import socket
import urllib.request
import json
from flask import Flask, render_template, jsonify, request
from config import Config

app = Flask(__name__, static_folder="../../design-system", static_url_path="/design-system")
app.config.from_object(Config)

def check_app_health(port):
    url = f"http://127.0.0.1:{port}/__whoami"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'SovereignGatewayCheck/1.0'})
        with urllib.request.urlopen(req, timeout=0.6) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode('utf-8'))
                return {"online": True, "name": data.get("name", "Unknown"), "status": "Healthy"}
    except Exception:
        pass
    
    # Fallback TCP check if __whoami is missing
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.3)
    result = sock.connect_ex(('127.0.0.1', port))
    sock.close()
    if result == 0:
        return {"online": True, "name": "Active Port", "status": "Port Open"}
    return {"online": False, "name": "-", "status": "Offline"}

@app.route("/")
def index():
    return render_template("index.html", apps=Config.APPS)

@app.route("/api/health")
def health_api():
    health_results = {}
    for app_info in Config.APPS:
        health_results[app_info["port"]] = check_app_health(app_info["port"])
    return jsonify(health_results)

@app.route("/__whoami")
def whoami():
    return jsonify({
        "name": "Sovereign Gateway Hub",
        "port": Config.PORT,
        "category": "Ecosystem Gateway",
        "status": "operational"
    })

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=Config.PORT, debug=Config.DEBUG)
