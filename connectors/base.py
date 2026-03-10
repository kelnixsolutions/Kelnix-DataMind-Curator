from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseConnector(ABC):
    """Abstract base for all data source connectors."""

    source_type: str = "unknown"

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to the data source."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Close the connection."""

    @abstractmethod
    async def test_connection(self) -> dict[str, Any]:
        """Test connectivity. Returns {"connected": bool, "message": str, "sample_tables": [...]}."""

    @abstractmethod
    async def list_tables(self) -> list[str]:
        """List available tables/collections."""

    @abstractmethod
    async def get_schema(self, table: str) -> list[dict[str, str]]:
        """Get column schema for a table. Returns [{"name": ..., "type": ...}, ...]."""

    @abstractmethod
    async def execute_query(self, sql: str, params: list | None = None) -> dict[str, Any]:
        """Execute a SQL query. Returns {"columns": [...], "rows": [[...], ...], "row_count": int}."""

    @abstractmethod
    async def fetch_rows(
        self, table: str, limit: int = 100, offset: int = 0, filters: dict | None = None
    ) -> dict[str, Any]:
        """Fetch rows from a table with optional filters."""

    async def get_table_count(self, table: str) -> int:
        """Get total row count for a table."""
        result = await self.execute_query(f"SELECT COUNT(*) as cnt FROM {table}")
        return result["rows"][0][0] if result["rows"] else 0
