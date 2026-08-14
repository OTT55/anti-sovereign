# PORT REGISTRY — Anti-Sovereign Infrastructure

**Single Source of Truth for Port Allocations across Anti-Sovereign & Sovereign Stack Ecosystem.**

## Port Blocks

| Block | Track / Service Category | Description |
|-------|--------------------------|-------------|
| **5000–5099** | **Gateway & CreativeOS** | System Gateway (5000), FrameVault, FilmCrew, RightsForge, CreatorStack, OTT Studio |
| **5100–5199** | **Sovereign Stack Companies** | Anti-sovereign app MVPs & production infrastructure micro-services |
| **5200–5299** | **AI Labs & Neural Engines** | Frontier AI connectors, local LLM/Ollama nodes, Noyron/Claude bridge endpoints |
| **5900–5999** | **Tools & Dev Utilities** | DB Inspector (5900), scratch testing endpoints |

## Active Allocations

### Gateway & CreativeOS (50xx)

| Port | Service Name | Directory / Location | Status |
|------|--------------|----------------------|--------|
| **5000** | Sovereign Gateway Hub | `companies/gateway/` | Active |
| 5001 | FrameVault | `companies/creativeos/framevault/` | Active |
| 5002 | FilmCrew | `companies/creativeos/filmcrew/` | Active |
| 5003 | RightsForge | `companies/creativeos/rightsforge/` | Active |
| 5005 | CreatorStack | `companies/creativeos/creatorstack/` | Active |
| 5006 | OTT Studio | `companies/creativeos/ott-studio/` | Active |

### Sovereign Stack Companies (51xx)

| Port | Company App | Category | Directory | Status |
|------|-------------|----------|-----------|--------|
| **5101** | Canonchain | Rights Registry | `companies/canonchain/` | Production |
| **5102** | Veridact | Truth Infrastructure | `companies/veridact/` | Production |
| **5103** | Nullform | Zero-Knowledge Identity | `companies/nullform/` | Production |
| **5104** | Clearpath | Compliance Engine | `companies/clearpath/` | Production |
| **5105** | Sovereign Edit | Film Provenance | `companies/sovereign-edit/` | Production |
| **5106** | Strata Finance | Capital Settlement | `companies/strata-finance/` | Production |
| **5107** | ContextCore | RAG & Refineries | `companies/contextcore/` | Production |
| **5108** | ArcVault | IP Arbitrage | `companies/arcvault/` | Production |
| **5109** | Story Atlas | Canon Engine & Workspace | `companies/creativeos/story-atlas/` | Production |

### AI Labs & Neural Connectors (52xx)

| Port | Service Name | Description | Status |
|------|--------------|-------------|--------|
| **5200** | AI Labs Connector | Frontier AI Lab Gateway (Noyron, Claude, Local Open-Weights) | Active |
| **5201** | Excess Engine MCP Bridge | Model Context Protocol gateway to local engines | Planned |

---

## Port Health Verification

Run the port status check tool:

```bash
python scripts/check_ports.py
```
