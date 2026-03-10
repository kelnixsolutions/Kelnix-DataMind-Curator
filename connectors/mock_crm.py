from __future__ import annotations

import random
from typing import Any

from connectors.base import BaseConnector

# Realistic mock data for demos and testing
_COMPANIES = [
    {"id": 1, "name": "Acme Corp", "industry": "Manufacturing", "revenue": 12500000, "employees": 450, "country": "US", "created_at": "2023-01-15"},
    {"id": 2, "name": "TechVista Solutions", "industry": "Software", "revenue": 8200000, "employees": 120, "country": "US", "created_at": "2023-03-22"},
    {"id": 3, "name": "GreenLeaf Bio", "industry": "Biotech", "revenue": 3100000, "employees": 65, "country": "UK", "created_at": "2023-05-10"},
    {"id": 4, "name": "Nordic Finance AB", "industry": "Finance", "revenue": 45000000, "employees": 800, "country": "SE", "created_at": "2023-06-01"},
    {"id": 5, "name": "CloudPeak Analytics", "industry": "Software", "revenue": 5600000, "employees": 90, "country": "US", "created_at": "2023-07-18"},
    {"id": 6, "name": "Sakura Motors", "industry": "Automotive", "revenue": 98000000, "employees": 2200, "country": "JP", "created_at": "2023-08-05"},
    {"id": 7, "name": "Berlin Digital GmbH", "industry": "Marketing", "revenue": 2800000, "employees": 45, "country": "DE", "created_at": "2023-09-12"},
    {"id": 8, "name": "Oceanic Shipping Ltd", "industry": "Logistics", "revenue": 67000000, "employees": 1500, "country": "SG", "created_at": "2023-10-30"},
]

_CONTACTS = [
    {"id": 1, "company_id": 1, "name": "Sarah Chen", "email": "sarah@acme.com", "role": "CTO", "phone": "+1-555-0101"},
    {"id": 2, "company_id": 1, "name": "James Wilson", "email": "james@acme.com", "role": "VP Sales", "phone": "+1-555-0102"},
    {"id": 3, "company_id": 2, "name": "Maria Garcia", "email": "maria@techvista.com", "role": "CEO", "phone": "+1-555-0201"},
    {"id": 4, "company_id": 3, "name": "Oliver Smith", "email": "oliver@greenleaf.co.uk", "role": "Head of R&D", "phone": "+44-20-5550301"},
    {"id": 5, "company_id": 4, "name": "Erik Johansson", "email": "erik@nordicfinance.se", "role": "CFO", "phone": "+46-8-5550401"},
    {"id": 6, "company_id": 5, "name": "Priya Patel", "email": "priya@cloudpeak.io", "role": "CTO", "phone": "+1-555-0501"},
    {"id": 7, "company_id": 6, "name": "Yuki Tanaka", "email": "yuki@sakuramotors.jp", "role": "VP Engineering", "phone": "+81-3-5550601"},
    {"id": 8, "company_id": 7, "name": "Max Mueller", "email": "max@berlindigital.de", "role": "Managing Director", "phone": "+49-30-5550701"},
    {"id": 9, "company_id": 8, "name": "Li Wei", "email": "wei@oceanicshipping.sg", "role": "COO", "phone": "+65-5550801"},
    {"id": 10, "company_id": 2, "name": "David Kim", "email": "david@techvista.com", "role": "Lead Engineer", "phone": "+1-555-0202"},
]

_DEALS = [
    {"id": 1, "company_id": 1, "contact_id": 1, "title": "Enterprise License Q1", "value": 250000, "stage": "closed_won", "close_date": "2024-03-15"},
    {"id": 2, "company_id": 2, "contact_id": 3, "title": "Platform Migration", "value": 180000, "stage": "negotiation", "close_date": "2024-06-30"},
    {"id": 3, "company_id": 4, "contact_id": 5, "title": "Risk Analytics Suite", "value": 520000, "stage": "proposal", "close_date": "2024-08-15"},
    {"id": 4, "company_id": 5, "contact_id": 6, "title": "Data Pipeline Setup", "value": 95000, "stage": "closed_won", "close_date": "2024-02-28"},
    {"id": 5, "company_id": 6, "contact_id": 7, "title": "IoT Fleet Integration", "value": 1200000, "stage": "discovery", "close_date": "2024-12-01"},
    {"id": 6, "company_id": 8, "contact_id": 9, "title": "Route Optimization AI", "value": 340000, "stage": "closed_lost", "close_date": "2024-04-10"},
    {"id": 7, "company_id": 1, "contact_id": 2, "title": "Support Renewal 2025", "value": 75000, "stage": "closed_won", "close_date": "2025-01-01"},
    {"id": 8, "company_id": 3, "contact_id": 4, "title": "Lab Data Platform", "value": 165000, "stage": "negotiation", "close_date": "2025-03-30"},
]

_TABLES = {
    "companies": _COMPANIES,
    "contacts": _CONTACTS,
    "deals": _DEALS,
}

_SCHEMAS = {
    "companies": [
        {"name": "id", "type": "integer"}, {"name": "name", "type": "text"},
        {"name": "industry", "type": "text"}, {"name": "revenue", "type": "numeric"},
        {"name": "employees", "type": "integer"}, {"name": "country", "type": "text"},
        {"name": "created_at", "type": "date"},
    ],
    "contacts": [
        {"name": "id", "type": "integer"}, {"name": "company_id", "type": "integer"},
        {"name": "name", "type": "text"}, {"name": "email", "type": "text"},
        {"name": "role", "type": "text"}, {"name": "phone", "type": "text"},
    ],
    "deals": [
        {"name": "id", "type": "integer"}, {"name": "company_id", "type": "integer"},
        {"name": "contact_id", "type": "integer"}, {"name": "title", "type": "text"},
        {"name": "value", "type": "numeric"}, {"name": "stage", "type": "text"},
        {"name": "close_date", "type": "date"},
    ],
}


class MockCRMConnector(BaseConnector):
    """Mock CRM connector with realistic sample data for demos."""

    source_type = "mock_crm"

    def __init__(self, **kwargs):
        self._connected = False

    async def connect(self) -> None:
        self._connected = True

    async def disconnect(self) -> None:
        self._connected = False

    async def test_connection(self) -> dict[str, Any]:
        return {
            "connected": True,
            "message": "Mock CRM connected. 3 tables, 26 records total.",
            "sample_tables": list(_TABLES.keys()),
        }

    async def list_tables(self) -> list[str]:
        return list(_TABLES.keys())

    async def get_schema(self, table: str) -> list[dict[str, str]]:
        schema = _SCHEMAS.get(table)
        if schema is None:
            raise ValueError(f"Table '{table}' not found in mock CRM")
        return schema

    async def execute_query(self, sql: str, params: list | None = None) -> dict[str, Any]:
        sql_lower = sql.lower().strip()

        # Simple SQL parser for mock data
        for table_name, data in _TABLES.items():
            if table_name in sql_lower:
                if not data:
                    return {"columns": [], "rows": [], "row_count": 0}

                columns = list(data[0].keys())
                rows = data

                # Handle WHERE clause
                if "where" in sql_lower:
                    rows = self._filter_rows(sql_lower, rows)

                # Handle ORDER BY
                if "order by" in sql_lower:
                    rows = self._order_rows(sql_lower, rows)

                # Handle LIMIT
                limit = self._extract_limit(sql_lower)
                if limit:
                    rows = rows[:limit]

                # Handle COUNT(*)
                if "count(*)" in sql_lower or "count(1)" in sql_lower:
                    return {"columns": ["count"], "rows": [[len(rows)]], "row_count": 1}

                result_rows = [[row[col] for col in columns] for row in rows]
                return {"columns": columns, "rows": result_rows, "row_count": len(result_rows)}

        return {"columns": [], "rows": [], "row_count": 0}

    async def fetch_rows(
        self, table: str, limit: int = 100, offset: int = 0, filters: dict | None = None
    ) -> dict[str, Any]:
        data = _TABLES.get(table)
        if data is None:
            raise ValueError(f"Table '{table}' not found")

        rows = data
        if filters:
            rows = [r for r in rows if all(r.get(k) == v for k, v in filters.items())]

        total = len(rows)
        rows = rows[offset: offset + limit]
        columns = list(data[0].keys()) if data else []
        result_rows = [[row[col] for col in columns] for row in rows]

        return {
            "columns": columns,
            "rows": result_rows,
            "row_count": len(result_rows),
            "total_available": total,
        }

    def _filter_rows(self, sql: str, rows: list[dict]) -> list[dict]:
        """Basic WHERE clause filtering."""
        try:
            where_part = sql.split("where", 1)[1]
            for kw in ("order", "limit", "group"):
                if kw in where_part:
                    where_part = where_part.split(kw)[0]

            conditions = where_part.strip().split(" and ")
            filtered = rows
            for cond in conditions:
                cond = cond.strip()
                for op in (">=", "<=", "!=", "=", ">", "<"):
                    if op in cond:
                        parts = cond.split(op, 1)
                        col = parts[0].strip().strip("'\"")
                        val = parts[1].strip().strip("'\"")
                        try:
                            val_num = float(val)
                        except ValueError:
                            val_num = None

                        if op == "=":
                            filtered = [r for r in filtered if str(r.get(col, "")) == val]
                        elif op == "!=" :
                            filtered = [r for r in filtered if str(r.get(col, "")) != val]
                        elif op == ">" and val_num is not None:
                            filtered = [r for r in filtered if (r.get(col, 0) or 0) > val_num]
                        elif op == ">=" and val_num is not None:
                            filtered = [r for r in filtered if (r.get(col, 0) or 0) >= val_num]
                        elif op == "<" and val_num is not None:
                            filtered = [r for r in filtered if (r.get(col, 0) or 0) < val_num]
                        elif op == "<=" and val_num is not None:
                            filtered = [r for r in filtered if (r.get(col, 0) or 0) <= val_num]
                        break
            return filtered
        except Exception:
            return rows

    def _order_rows(self, sql: str, rows: list[dict]) -> list[dict]:
        try:
            order_part = sql.split("order by")[1]
            for kw in ("limit",):
                if kw in order_part:
                    order_part = order_part.split(kw)[0]
            col = order_part.strip().split()[0].strip()
            desc = "desc" in order_part.lower()
            return sorted(rows, key=lambda r: r.get(col, ""), reverse=desc)
        except Exception:
            return rows

    def _extract_limit(self, sql: str) -> int | None:
        try:
            if "limit" in sql:
                return int(sql.split("limit")[1].strip().split()[0])
        except Exception:
            pass
        return None
