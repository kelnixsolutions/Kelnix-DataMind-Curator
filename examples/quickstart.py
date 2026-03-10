"""
Kelnix DataMind Curator — Python quickstart example.

1. Register for an API key
2. Connect a data source (mock CRM for demo)
3. Query with natural language
4. Clean and deduplicate data
5. Build AI-ready context
"""
import httpx

BASE = "https://datamind-api.kelnix.org"

# 1. Register
resp = httpx.post(f"{BASE}/register", json={"agent_name": "My Agent"})
api_key = resp.json()["api_key"]
headers = {"X-API-Key": api_key}
print(f"API Key: {api_key}")

# 2. Connect mock CRM
resp = httpx.post(
    f"{BASE}/sources/connect",
    json={"source_type": "mock_crm", "name": "Demo CRM"},
    headers=headers,
)
source_id = resp.json()["source_id"]
print(f"Source: {source_id}")

# 3. Query with natural language
resp = httpx.post(
    f"{BASE}/data/query",
    json={
        "source_id": source_id,
        "query": "top 3 companies by revenue",
    },
    headers=headers,
)
print(f"Query result: {resp.json()['rows']}")

# 4. Check balance
resp = httpx.get(f"{BASE}/balance", headers=headers)
print(f"Balance: {resp.json()}")
