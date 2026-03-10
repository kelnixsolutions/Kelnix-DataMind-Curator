from __future__ import annotations

from typing import Any

from connectors.base import BaseConnector


class PostgreSQLConnector(BaseConnector):
    source_type = "postgresql"

    def __init__(self, connection_string: str | None = None, **kwargs):
        self._dsn = connection_string or ""
        self._pool = None

    async def connect(self) -> None:
        import asyncpg
        self._pool = await asyncpg.create_pool(self._dsn, min_size=1, max_size=5)

    async def disconnect(self) -> None:
        if self._pool:
            await self._pool.close()
            self._pool = None

    async def test_connection(self) -> dict[str, Any]:
        try:
            if not self._pool:
                await self.connect()
            async with self._pool.acquire() as conn:
                version = await conn.fetchval("SELECT version()")
                tables = await self._fetch_tables(conn)
            return {
                "connected": True,
                "message": f"Connected. {version.split(',')[0] if version else 'PostgreSQL'}",
                "sample_tables": tables[:20],
            }
        except Exception as e:
            return {"connected": False, "message": str(e), "sample_tables": None}

    async def _fetch_tables(self, conn) -> list[str]:
        rows = await conn.fetch(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' ORDER BY table_name"
        )
        return [r["table_name"] for r in rows]

    async def list_tables(self) -> list[str]:
        async with self._pool.acquire() as conn:
            return await self._fetch_tables(conn)

    async def get_schema(self, table: str) -> list[dict[str, str]]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT column_name, data_type FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = $1 ORDER BY ordinal_position",
                table,
            )
        return [{"name": r["column_name"], "type": r["data_type"]} for r in rows]

    async def execute_query(self, sql: str, params: list | None = None) -> dict[str, Any]:
        async with self._pool.acquire() as conn:
            if params:
                stmt = await conn.prepare(sql)
                rows = await stmt.fetch(*params)
            else:
                rows = await conn.fetch(sql)

            if not rows:
                return {"columns": [], "rows": [], "row_count": 0}

            columns = list(rows[0].keys())
            data = [[_serialize(row[col]) for col in columns] for row in rows]
            return {"columns": columns, "rows": data, "row_count": len(data)}

    async def fetch_rows(
        self, table: str, limit: int = 100, offset: int = 0, filters: dict | None = None
    ) -> dict[str, Any]:
        where_parts: list[str] = []
        params: list = []
        if filters:
            for i, (key, val) in enumerate(filters.items(), 1):
                where_parts.append(f"{key} = ${i}")
                params.append(val)

        where_clause = f" WHERE {' AND '.join(where_parts)}" if where_parts else ""
        idx = len(params) + 1

        sql = f"SELECT * FROM {table}{where_clause} LIMIT ${idx} OFFSET ${idx + 1}"
        params.extend([limit, offset])

        result = await self.execute_query(sql, params)
        total = await self.get_table_count(table)
        result["total_available"] = total
        return result


def _serialize(val: Any) -> Any:
    """Convert asyncpg types to JSON-safe values."""
    if val is None:
        return None
    if isinstance(val, (int, float, str, bool)):
        return val
    return str(val)
