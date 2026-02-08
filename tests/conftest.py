"""Pytest configuration and fixtures."""

import pytest


@pytest.fixture
def mock_gemini_response():
    """Mock Gemini API response."""
    return {
        "text": "This is a mock response",
        "stats": {
            "prompt_tokens": 100,
            "response_tokens": 50,
            "total_tokens": 150,
        },
    }


@pytest.fixture
def sample_code():
    """Sample code for analysis tests."""
    return '''
def calculate_total(items):
    total = 0
    for item in items:
        total += item["price"]
    return total
'''


@pytest.fixture
def sample_config():
    """Sample configuration for tests."""
    return {
        "transport": "stdio",
        "server_port": 8765,
        "enable_swarm": True,
        "enable_debate": True,
    }
