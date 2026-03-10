<p align="center">
  <img src="Kelnix Datamind Curator.png" alt="Kelnix DataMind Curator" width="200" />
</p>

<h1 align="center">Kelnix DataMind Curator</h1>

<p align="center">
  <strong>🧠 AI-Ready Data & Context Engineering API</strong><br/>
  Connect any data source, query with natural language, clean and standardize data, build AI-ready context packages, and protect privacy with automated PII redaction.
</p>

<p align="center">
  <a href="https://datamind-api.kelnix.org/docs">📖 API Docs</a> •
  <a href="https://datamind-api.kelnix.org/pricing">💰 Pricing</a> •
  <a href="https://kelnix.org">🌐 Website</a>
</p>

---

One API to unify, clean, and serve your data to AI agents. ⚡

## 🚀 Quick Start

```bash
# 1. Register (free — 25 credits, no credit card)
curl -X POST https://datamind-api.kelnix.org/register \
  -H "Content-Type: application/json" \
  -d '{"agent_name": "My Agent"}'

# 2. Connect a data source (mock CRM for demo)
curl -X POST https://datamind-api.kelnix.org/sources/connect \
  -H "X-API-Key: dm_YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"source_type": "mock_crm", "name": "Demo CRM"}'

# 3. Query with natural language
curl -X POST https://datamind-api.kelnix.org/data/query \
  -H "X-API-Key: dm_YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"source_id": "YOUR_SOURCE_ID", "query": "top 5 companies by revenue"}'
```

## 🔌 MCP Integration

Works with Claude Desktop, Cursor, VS Code, and any MCP-compatible client.

### Claude Desktop / Cursor

Add to your MCP config:

```json
{
  "mcpServers": {
    "kelnix-datamind-curator": {
      "url": "https://datamind-api.kelnix.org/stream/mcp/",
      "headers": {
        "X-API-Key": "dm_YOUR_API_KEY"
      }
    }
  }
}
```

### Smithery

```bash
npx -y @smithery/cli@latest install @kelnix/kelnix-datamind-curator --client claude
```

## 🛠️ Tools

| Tool | Description | Cost |
|------|-------------|------|
| `sources.connect` | 🔗 Connect a data source (PostgreSQL, MySQL, CRM, API) | 1 credit |
| `sources.list` | 📋 List connected data sources | free |
| `sources.test` | ✅ Test source connectivity | free |
| `data.query` | 💬 Query data with natural language or SQL | 2 credits |
| `data.fetch` | 📥 Fetch raw rows with filters & pagination | 1 credit |
| `data.search` | 🔍 Semantic vector search across indexed data | 2 credits |
| `pipeline.clean` | 🧹 Standardize dates, phones, emails, currencies | 2 credits |
| `pipeline.deduplicate` | 🔄 Remove duplicate records | 1 credit |
| `pipeline.redact_pii` | 🔒 Auto-detect and redact PII | 1 credit |
| `context.build` | 🧠 Build AI-ready context for RAG pipelines | 3 credits |
| `context.summarize` | 📊 AI-powered dataset summary with insights | 2 credits |
| `credits.check_balance` | 💳 Check credits and plan | free |

## 📦 Supported Data Sources

- 🐘 **PostgreSQL** — Full SQL support with schema introspection
- 🐬 **MySQL** — Coming soon
- 🏢 **Mock CRM** — Built-in demo with companies, contacts, and deals
- 📄 **CSV** — Coming soon
- 🌐 **JSON API** — Coming soon

## 💰 Pricing

| Credits | Price | Per Credit |
|---------|-------|------------|
| 25 | 🎁 Free | on signup |
| 100 | $8 | $0.080 |
| 500 | $30 | $0.060 |
| 1,000 | $50 | $0.050 |
| 5,000 | $200 | $0.040 |
| 10,000 | $400 | $0.040 |

Monthly plans: **Basic** (200/mo, $15) · **Pro** (2,000/mo, $99)

💳 Pay with Stripe (cards) or 🪙 300+ cryptocurrencies.

## 📖 API Docs

Interactive Swagger docs: [datamind-api.kelnix.org/docs](https://datamind-api.kelnix.org/docs)

## 🏗️ Self-Hosting

```bash
git clone https://github.com/kelnixsolutions/Kelnix-DataMind-Curator.git
cd Kelnix-DataMind-Curator
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # edit with your keys
uvicorn app:app --host 0.0.0.0 --port 8001
```

## 🏛️ Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  MCP Clients │     │  REST API    │     │  Registries  │
│ Claude/Cursor│────▶│  FastAPI     │◀────│ Smithery/etc │
└──────────────┘     └──────┬───────┘     └──────────────┘
                            │
                 ┌──────────┼──────────┐
                 │          │          │
          ┌──────▼──┐ ┌────▼────┐ ┌───▼──────┐
          │Connectors│ │Pipeline │ │ Context  │
          │ PG/CRM  │ │Clean/PII│ │Build/NLQ │
          └─────────┘ └─────────┘ └──────────┘
                 │          │          │
          ┌──────▼──┐ ┌────▼────┐ ┌───▼──────┐
          │ SQLite  │ │ Redis   │ │ ChromaDB │
          │ Billing │ │ Cache   │ │ Vectors  │
          └─────────┘ └─────────┘ └──────────┘
```

## 📜 License

Proprietary — [Kelnix Solutions](https://kelnix.org)
