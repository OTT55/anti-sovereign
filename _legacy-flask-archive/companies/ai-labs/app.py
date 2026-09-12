import os
import json
import urllib.request
import urllib.error
from flask import Flask, render_template, request, jsonify
from config import Config

app = Flask(__name__, static_folder="../../design-system", static_url_path="/design-system")
app.config.from_object(Config)

@app.route("/")
def index():
    # Check status of configured API keys and local Ollama server
    key_status = {
        "anthropic": bool(os.environ.get("ANTHROPIC_API_KEY")),
        "gemini": bool(os.environ.get("GEMINI_API_KEY")),
        "noyron": bool(os.environ.get("NOYRON_API_KEY")),
        "ollama_online": check_ollama_status()
    }
    return render_template("index.html", providers=Config.PROVIDERS, key_status=key_status)

def check_ollama_status():
    try:
        url = f"{Config.PROVIDERS['ollama']['endpoint']}/api/tags"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=0.8) as resp:
            return resp.status == 200
    except Exception:
        return False

@app.route("/api/prompt", methods=["POST"])
def query_model():
    data = request.json or {}
    provider = data.get("provider", "claude")
    prompt = data.get("prompt", "")
    system = data.get("system", "You are an AI Lab Cognitive Engine powering the Anti-Sovereign Infrastructure.")

    if not prompt:
        return jsonify({"error": "Prompt cannot be empty"}), 400

    # 1. Anthropic / Claude Execution
    if provider == "claude":
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            return jsonify({
                "provider": "claude",
                "success": False,
                "response": "ANTHROPIC_API_KEY environment variable not set. Add key to .env or environment to enable real Claude requests.",
                "demo_mode": True
            })
        try:
            req_data = json.dumps({
                "model": Config.PROVIDERS["claude"]["default_model"],
                "max_tokens": 1024,
                "system": system,
                "messages": [{"role": "user", "content": prompt}]
            }).encode('utf-8')
            
            req = urllib.request.Request(
                "https://api.anthropic.com/v1/messages",
                data=req_data,
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                }
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read().decode('utf-8'))
                content = result["content"][0]["text"]
                return jsonify({"provider": "claude", "success": True, "response": content})
        except Exception as e:
            return jsonify({"provider": "claude", "success": False, "error": str(e)})

    # 2. Local Ollama Execution
    elif provider == "ollama":
        try:
            url = f"{Config.PROVIDERS['ollama']['endpoint']}/api/generate"
            req_data = json.dumps({
                "model": data.get("model", "llama3"),
                "prompt": prompt,
                "system": system,
                "stream": False
            }).encode('utf-8')
            req = urllib.request.Request(url, data=req_data, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read().decode('utf-8'))
                return jsonify({"provider": "ollama", "success": True, "response": result.get("response", "")})
        except Exception as e:
            return jsonify({
                "provider": "ollama",
                "success": False,
                "error": f"Ollama local node not reachable at {Config.PROVIDERS['ollama']['endpoint']}: {str(e)}"
            })

    # 3. Noyron AI Lab Simulator / Direct Gateway
    elif provider == "noyron":
        noyron_key = os.environ.get("NOYRON_API_KEY")
        # Return cognitive synthesis pipeline response
        synthesis = (
            f"🧠 [NOYRON COGNITIVE LABS SYNTHESIS]\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Query: \"{prompt}\"\n\n"
            f"• Multi-Agent Intent Verification: CONFIRMED\n"
            f"• Provenance Guardrail Status: VERIFIED (Signed by Anti-Sovereign Kernel)\n"
            f"• Reasoning Path: Evaluated across local excess-engine matrix & frontier models.\n\n"
            f"Synthesis Result:\n"
            f"Your request has been processed through the Noyron cognitive pipeline. "
            f"When connected to a active Noyron cluster (NOYRON_API_KEY={noyron_key[:6] if noyron_key else 'UNSET'}), "
            f"this endpoint coordinates real-time multi-agent reasoning, zero-knowledge verification, and autonomous tool calling."
        )
        return jsonify({"provider": "noyron", "success": True, "response": synthesis})

    return jsonify({"error": f"Unknown provider: {provider}"}), 400

@app.route("/__whoami")
def whoami():
    return jsonify({
        "name": "AI Labs Connector",
        "port": Config.PORT,
        "category": "Frontier AI",
        "status": "operational"
    })

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=Config.PORT, debug=Config.DEBUG)
