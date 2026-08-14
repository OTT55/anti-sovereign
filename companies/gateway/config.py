import os

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "anti-sovereign-gateway-secret-key-2026")
    PORT = int(os.environ.get("GATEWAY_PORT", 5000))
    DEBUG = os.environ.get("FLASK_DEBUG", "True").lower() in ("true", "1")
    
    APPS = [
        {"id": "gateway", "name": "Sovereign Gateway Hub", "port": 5000, "category": "Gateway", "accent": "#6366F1", "desc": "Central ecosystem launchpad & live process monitor"},
        {"id": "canonchain", "name": "Canonchain", "port": 5101, "category": "Rights Registry", "accent": "#F59E0B", "desc": "SHA-256 IP registry, Merkle inclusion proofs & Certificates"},
        {"id": "veridact", "name": "Veridact", "port": 5102, "category": "Truth Infrastructure", "accent": "#7C3AED", "desc": "Capture attestation — real camera verification vs AI generated media"},
        {"id": "nullform", "name": "Nullform", "port": 5103, "category": "Identity Layer", "accent": "#10B981", "desc": "Zero-knowledge Schnorr identity verification (key stays client-side)"},
        {"id": "clearpath", "name": "Clearpath", "port": 5104, "category": "Compliance Routing", "accent": "#06B6D4", "desc": "Jurisdiction rules engine with audit-chained compliance routing"},
        {"id": "sovereign-edit", "name": "Sovereign Edit", "port": 5105, "category": "Certification", "accent": "#EC4899", "desc": "Hash-linked film provenance chain & authenticity certificate"},
        {"id": "strata-finance", "name": "Strata Finance", "port": 5106, "category": "Capital Settlement", "accent": "#059669", "desc": "Integer cents waterfall revenue settlement & double-entry ledger"},
        {"id": "contextcore", "name": "ContextCore", "port": 5107, "category": "Data Refineries", "accent": "#3B82F6", "desc": "Local TF-IDF RAG corpora & distribution intelligence engines"},
        {"id": "arcvault", "name": "ArcVault", "port": 5108, "category": "IP Arbitrage", "accent": "#8B5CF6", "desc": "Public-domain IP adaptation & genre synthesis engine"},
        {"id": "story-atlas", "name": "Story Atlas", "port": 5109, "category": "Creative Intelligence", "accent": "#C1121F", "desc": "Worldbuilding universe DB, timeline graph & Canon auditor"},
        {"id": "ai-labs", "name": "AI Labs Connector", "port": 5200, "category": "Frontier AI", "accent": "#F43F5E", "desc": "Noyron, Claude & Local Open-Weights Frontier AI Integration Hub"},
    ]
