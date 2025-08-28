from unittest.mock import AsyncMock, patch

import pytest

from status import app


@pytest.fixture
def test_client():
    """Create a test client for the Quart app."""
    return app.test_client()


@pytest.mark.asyncio
async def test_readiness_endpoint(test_client):
    """Test the /readyz endpoint."""
    response = await test_client.get("/readyz")
    assert response.status_code == 200
    assert response.response.data == b"OK"


@pytest.mark.asyncio
async def test_liveness_endpoint(test_client):
    """Test the /livez endpoint."""
    response = await test_client.get("/livez")
    assert response.status_code == 200
    assert response.response.data == b"OK"


@pytest.mark.asyncio
@patch("status.httpx.get")
async def test_todays_burns(mock_get, test_client):
    """Test the /api/todays-burns endpoint with mocked HTTP response."""
    mock_get.return_value = AsyncMock(
        status_code=200,
        content=b'<FeatureCollection numberOfFeatures="5"></FeatureCollection>',
    )

    response = await test_client.get("/api/todays-burns")
    assert response.status_code == 200
    assert b"5" in response.response.data

