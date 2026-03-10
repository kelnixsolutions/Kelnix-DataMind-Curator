from connectors.base import BaseConnector
from connectors.postgresql import PostgreSQLConnector
from connectors.mock_crm import MockCRMConnector

CONNECTOR_REGISTRY: dict[str, type[BaseConnector]] = {
    "postgresql": PostgreSQLConnector,
    "mock_crm": MockCRMConnector,
}


def get_connector(source_type: str, **kwargs) -> BaseConnector:
    cls = CONNECTOR_REGISTRY.get(source_type)
    if cls is None:
        raise ValueError(f"Unsupported source type: {source_type}. Available: {list(CONNECTOR_REGISTRY.keys())}")
    return cls(**kwargs)
