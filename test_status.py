from unittest.mock import AsyncMock, MagicMock, patch

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
async def test_todays_burns(test_client):
    """Test the /api/todays-burns endpoint with mocked HTTP response."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.content = b'<FeatureCollection numberOfFeatures="5"></FeatureCollection>'

    mock_session = AsyncMock()
    mock_session.get.return_value = mock_response

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_session)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("status.get_anonymous_session", return_value=mock_client):
        response = await test_client.get("/api/todays-burns")

    assert response.status_code == 200
    assert b"5" in response.response.data
