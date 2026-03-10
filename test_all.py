"""
Comprehensive test suite for Kelnix DataMind Curator.
Run: python -m pytest test_all.py -v
"""
from __future__ import annotations

import json
import os
import sys
import asyncio

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(__file__))


# ── Unit tests ──────────────────────────────────────────────────────────

class TestDedup:
    def test_basic_dedup(self):
        from pipeline.dedup import deduplicate

        records = [
            {"name": "Alice", "email": "alice@test.com"},
            {"name": "Bob", "email": "bob@test.com"},
            {"name": "Alice", "email": "alice@test.com"},
        ]
        result = deduplicate(records)
        assert result["records_in"] == 3
        assert result["records_out"] == 2
        assert result["duplicates_removed"] == 1

    def test_dedup_with_keys(self):
        from pipeline.dedup import deduplicate

        records = [
            {"name": "Alice", "email": "alice@test.com", "age": 30},
            {"name": "Alice", "email": "alice@test.com", "age": 31},
        ]
        result = deduplicate(records, keys=["email"])
        assert result["records_out"] == 1

    def test_no_duplicates(self):
        from pipeline.dedup import deduplicate

        records = [{"id": 1}, {"id": 2}, {"id": 3}]
        result = deduplicate(records)
        assert result["duplicates_removed"] == 0


class TestFormatter:
    def test_date_standardization(self):
        from pipeline.formatter import standardize

        records = [{"created_at": "03/15/2024"}, {"created_at": "2024-03-16"}]
        result = standardize(records, rules={"created_at": "date"})
        assert result["cleaned_data"][0]["created_at"] == "2024-03-15"

    def test_email_lowercase(self):
        from pipeline.formatter import standardize

        records = [{"email": "  Alice@Test.COM  "}]
        result = standardize(records, rules={"email": "email"})
        assert result["cleaned_data"][0]["email"] == "alice@test.com"

    def test_currency_parsing(self):
        from pipeline.formatter import standardize

        records = [{"amount": "$1,234.56"}]
        result = standardize(records, rules={"amount": "currency"})
        assert result["cleaned_data"][0]["amount"] == 1234.56

    def test_auto_detect(self):
        from pipeline.formatter import standardize

        records = [{"email": "TEST@foo.com", "phone": "(555) 123-4567", "revenue": "$100"}]
        result = standardize(records)
        assert result["records_out"] == 1


class TestPIIRedactor:
    def test_auto_detect_pii(self):
        from pipeline.pii_redactor import redact_pii

        records = [{"name": "Alice", "email": "alice@test.com", "phone": "+1-555-0101"}]
        result = redact_pii(records)
        assert result["redacted_data"][0]["email"] == "[REDACTED]"
        assert result["redacted_data"][0]["name"] == "[REDACTED]"

    def test_explicit_fields(self):
        from pipeline.pii_redactor import redact_pii

        records = [{"name": "Bob", "company": "Acme"}]
        result = redact_pii(records, fields_to_redact=["name"])
        assert result["redacted_data"][0]["name"] == "[REDACTED]"
        assert result["redacted_data"][0]["company"] == "Acme"

    def test_regex_detection(self):
        from pipeline.pii_redactor import redact_pii

        records = [{"note": "Contact me at bob@example.com for details"}]
        result = redact_pii(records, fields_to_redact=[])
        assert "[REDACTED]" in result["redacted_data"][0]["note"]

    def test_custom_replacement(self):
        from pipeline.pii_redactor import redact_pii

        records = [{"email": "test@test.com"}]
        result = redact_pii(records, replacement="***")
        assert result["redacted_data"][0]["email"] == "***"


class TestMockCRM:
    def test_list_tables(self):
        from connectors.mock_crm import MockCRMConnector

        connector = MockCRMConnector()
        tables = asyncio.get_event_loop().run_until_complete(connector.list_tables())
        assert "companies" in tables
        assert "contacts" in tables
        assert "deals" in tables

    def test_fetch_companies(self):
        from connectors.mock_crm import MockCRMConnector

        connector = MockCRMConnector()
        result = asyncio.get_event_loop().run_until_complete(connector.fetch_rows("companies"))
        assert result["row_count"] == 8
        assert "name" in result["columns"]

    def test_fetch_with_filter(self):
        from connectors.mock_crm import MockCRMConnector

        connector = MockCRMConnector()
        result = asyncio.get_event_loop().run_until_complete(
            connector.fetch_rows("companies", filters={"industry": "Software"})
        )
        assert result["row_count"] == 2

    def test_execute_query(self):
        from connectors.mock_crm import MockCRMConnector

        connector = MockCRMConnector()
        result = asyncio.get_event_loop().run_until_complete(
            connector.execute_query("SELECT * FROM deals WHERE stage = 'closed_won'")
        )
        assert result["row_count"] == 3

    def test_count_query(self):
        from connectors.mock_crm import MockCRMConnector

        connector = MockCRMConnector()
        result = asyncio.get_event_loop().run_until_complete(
            connector.execute_query("SELECT COUNT(*) FROM contacts")
        )
        assert result["rows"][0][0] == 10

    def test_schema(self):
        from connectors.mock_crm import MockCRMConnector

        connector = MockCRMConnector()
        schema = asyncio.get_event_loop().run_until_complete(connector.get_schema("companies"))
        names = [c["name"] for c in schema]
        assert "name" in names
        assert "revenue" in names


class TestNLQ:
    def test_is_natural_language(self):
        from nlq_engine import is_natural_language

        assert is_natural_language("show me all customers") is True
        assert is_natural_language("what are the top deals?") is True
        assert is_natural_language("SELECT * FROM users") is False
        assert is_natural_language("select count(*) from orders") is False


class TestDB:
    def test_init_and_agent(self):
        import tempfile
        import db as _db

        # Use temp DB
        original = _db.DB_PATH
        _db.DB_PATH = tempfile.mktemp(suffix=".db")
        _db._local = __import__("threading").local()  # reset connections

        try:
            _db.init_db()

            # Create agent
            agent = _db.create_agent("Test Agent", org_id="test-org")
            assert agent["api_key"].startswith("dm_")
            assert agent["free_credits"] == 25

            # Check balance
            balance = _db.get_credit_balance(agent["api_key"])
            assert balance == 25

            # Deduct
            success = _db.atomic_deduct_if_sufficient(agent["api_key"], 5, "test")
            assert success is True
            assert _db.get_credit_balance(agent["api_key"]) == 20

            # Insufficient
            success = _db.atomic_deduct_if_sufficient(agent["api_key"], 100, "test")
            assert success is False

            # Source management
            _db.insert_source("src1", agent["api_key"], "mock_crm", "Test CRM")
            sources = _db.list_sources(agent["api_key"])
            assert len(sources) == 1
            assert sources[0]["name"] == "Test CRM"

        finally:
            _db.DB_PATH = original
            _db._local = __import__("threading").local()


class TestRedisCache:
    def test_memory_fallback(self):
        import redis_cache

        redis_cache.set("test_key", {"foo": "bar"}, ttl=10)
        result = redis_cache.get("test_key")
        assert result == {"foo": "bar"}

        redis_cache.delete("test_key")
        assert redis_cache.get("test_key") is None


class TestConnectorRegistry:
    def test_get_mock_crm(self):
        from connectors import get_connector

        conn = get_connector("mock_crm")
        assert conn.source_type == "mock_crm"

    def test_get_postgresql(self):
        from connectors import get_connector

        conn = get_connector("postgresql", connection_string="postgresql://localhost/test")
        assert conn.source_type == "postgresql"

    def test_unknown_type(self):
        from connectors import get_connector
        import pytest

        try:
            get_connector("oracle")
            assert False, "Should have raised"
        except ValueError:
            pass


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
