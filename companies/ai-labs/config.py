import os

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "ai-labs-connector-secret-key-2026")
    PORT = int(os.environ.get("AI_LABS_PORT", 5200))
    DEBUG = os.environ.get("FLASK_DEBUG", "True").lower() in ("true", "1")
    
    PROVIDERS = {
        "claude": {
            "name": "Anthropic (Claude 3.5 / Claude Sonnet / Opus)",
            "api_key_env": "ANTHROPIC_API_KEY",
            "default_model": "claude-3-5-sonnet-20241022",
            "type": "frontier"
        },
        "antigravity": {
            "name": "Google DeepMind (Gemini / Antigravity Agentic SDK)",
            "api_key_env": "GEMINI_API_KEY",
            "default_model": "gemini-1.5-pro",
            "type": "agentic"
        },
        "noyron": {
            "name": "Noyron AI Labs (Cognitive Engine)",
            "api_key_env": "NOYRON_API_KEY",
            "default_model": "noyron-v1-synthesis",
            "type": "cognitive"
        },
        "ollama": {
            "name": "Local Open-Weights (Ollama / Llama3 / Mistral / DeepSeek)",
            "endpoint": os.environ.get("OLLAMA_ENDPOINT", "http://localhost:11434"),
            "default_model": "llama3:latest",
            "type": "local"
        }
    }
