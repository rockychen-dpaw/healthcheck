"""Unit tests for all endpoints in the status.py Quart application."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from status import app

# --- Fixtures ---


@pytest.fixture
def test_client():
    """Create a test client for the Quart app."""
    return app.test_client()


# --- Helpers ---

# Minimal XML with 3 WMTS layers for /api/kmi-wmts-layers tests.
KMI_WMTS_XML = b'<Capabilities xmlns:wmts="http://www.opengis.net/wmts/1.0"><wmts:Layer/><wmts:Layer/><wmts:Layer/></Capabilities>'

# Minimal healthcheck dict mirroring the shape returned by get_healthcheck().
SAMPLE_HEALTHCHECK = {
    "server_time": "2026-01-01T00:00:00+08:00",
    "success": True,
    "errors": [],
    "latest_point": "2026-01-01T00:00:00+08:00",
    "latest_point_age_min": 5.0,
    "iridium_latest_point": "2026-01-01T00:00:00+08:00",
    "iridium_latest_point_age_min": 5.0,
    "iridium_loggedpoint_rate_min": 10,
    "tracplus_latest_point": "2026-01-01T00:00:00+08:00",
    "tracplus_latest_point_delay": 5.0,
    "tracplus_loggedpoint_rate_min": 10,
    "dfes_latest_point": "2026-01-01T00:00:00+08:00",
    "dfes_latest_point_delay": 5.0,
    "dfes_loggedpoint_rate_min": 10,
    "fleetcare_latest_point": "2026-01-01T00:00:00+08:00",
    "fleetcare_latest_point_delay": 5.0,
    "fleetcare_loggedpoint_rate_min": 10,
    "netstar_latest_point": "2026-01-01T00:00:00+08:00",
    "netstar_latest_point_delay": 5.0,
    "netstar_loggedpoint_rate_min": 10,
    "todays_burns_count": 5,
    "bfrs_profile_api_endpoint": True,
    "auth2_status": True,
    "sss_status": True,
}


def make_mock_client(status_code: int = 200, json_data=None, content: bytes = b"", raise_error: bool = False):
    """Build a mock httpx.AsyncClient usable as an async context manager.

    Returns a MagicMock whose __aenter__ yields a mock session whose .get()
    returns a mock response configured with the supplied parameters.
    """
    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.content = content
    if json_data is not None:
        mock_response.json.return_value = json_data
    if raise_error:
        mock_response.raise_for_status.side_effect = Exception("HTTP error")
    else:
        mock_response.raise_for_status = MagicMock()

    mock_session = AsyncMock()
    mock_session.get.return_value = mock_response

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_session)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


# --- Probe endpoints ---


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


# --- Root and aggregate endpoints ---


@pytest.mark.asyncio
async def test_index(test_client):
    """Test the / endpoint renders an HTML page."""
    response = await test_client.get("/")
    assert response.status_code == 200
    assert b"<html" in response.response.data.lower()


@pytest.mark.asyncio
async def test_json_success(test_client):
    """Test the /json endpoint returns a valid JSON healthcheck response."""
    with patch("status.get_healthcheck", new=AsyncMock(return_value=SAMPLE_HEALTHCHECK)):
        response = await test_client.get("/json")
    assert response.status_code == 200
    data = await response.get_json()
    assert data["success"] is True
    assert "server_time" in data


@pytest.mark.asyncio
async def test_json_error(test_client):
    """Test the /json endpoint returns a failure JSON when get_healthcheck raises."""
    with patch("status.get_healthcheck", new=AsyncMock(side_effect=Exception("failure"))):
        response = await test_client.get("/json")
    assert response.status_code == 200
    data = await response.get_json()
    assert data["success"] is False


@pytest.mark.asyncio
async def test_legacy_success(test_client):
    """Test the /legacy endpoint returns HTML with a success message."""
    with patch("status.get_healthcheck", new=AsyncMock(return_value=SAMPLE_HEALTHCHECK)):
        response = await test_client.get("/legacy")
    assert response.status_code == 200
    assert b"healthcheck succeeded" in response.response.data


@pytest.mark.asyncio
async def test_legacy_failure(test_client):
    """Test the /legacy endpoint includes a failure message when success=False."""
    data = {**SAMPLE_HEALTHCHECK, "success": False}
    with patch("status.get_healthcheck", new=AsyncMock(return_value=data)):
        response = await test_client.get("/legacy")
    assert response.status_code == 200
    assert b"something is wrong" in response.response.data


# --- /api/<source>/latest ---


@pytest.mark.asyncio
async def test_prtg_success(test_client):
    """Test the /prtg endpoint returns valid PRTG JSON with channels on success."""
    with patch("status.get_healthcheck", new=AsyncMock(return_value=SAMPLE_HEALTHCHECK)):
        response = await test_client.get("/prtg")
    assert response.status_code == 200
    data = await response.get_json()
    assert "prtg" in data
    assert data["prtg"]["error"] == 0
    assert data["prtg"]["text"] == "All checks passed"
    channels = data["prtg"]["result"]
    assert isinstance(channels, list)
    assert len(channels) > 0
    channel_names = [ch["channel"] for ch in channels]
    assert "All tracking devices delay" in channel_names
    assert "Iridium delay" in channel_names
    assert "BFRS status" in channel_names
    assert "Auth2 status" in channel_names
    assert "SSS status" in channel_names
    for ch in channels:
        assert "channel" in ch
        assert "value" in ch


@pytest.mark.asyncio
async def test_prtg_exception(test_client):
    """Test the /prtg endpoint returns an error PRTG response when get_healthcheck raises."""
    with patch("status.get_healthcheck", new=AsyncMock(side_effect=Exception("failure"))):
        response = await test_client.get("/prtg")
    assert response.status_code == 200
    body = await response.get_json()
    assert body["prtg"]["error"] == 1


@pytest.mark.asyncio
async def test_prtg_channel_error_on_null(test_client):
    """Test that channels have error=1 when their source values are None."""
    data = {
        **SAMPLE_HEALTHCHECK,
        "latest_point_age_min": None,
        "bfrs_profile_api_endpoint": None,
    }
    with patch("status.get_healthcheck", new=AsyncMock(return_value=data)):
        response = await test_client.get("/prtg")
    assert response.status_code == 200
    body = await response.get_json()
    channels = {ch["channel"]: ch for ch in body["prtg"]["result"]}
    assert channels["All tracking devices delay"].get("error") == 1
    assert channels["BFRS status"].get("error") == 1


@pytest.mark.asyncio
async def test_prtg_rate_channel_below_minimum(test_client):
    """Test that a rate channel has error=1 when its value is below the supplied minimum."""
    data = {**SAMPLE_HEALTHCHECK, "fleetcare_loggedpoint_rate_min": 0}
    with patch("status.get_healthcheck", new=AsyncMock(return_value=data)):
        response = await test_client.get("/prtg")
    assert response.status_code == 200
    body = await response.get_json()
    # Fleetcare tracking rate channel uses min_val=1 in build_prtg_channels
    channels = {ch["channel"]: ch for ch in body["prtg"]["result"]}
    assert channels["Fleetcare tracking rate"].get("error") == 1


@pytest.mark.asyncio
async def test_prtg_sss_status_false(test_client):
    """Test that the SSS status channel has error=1 and the top-level error is 1 when sss_status is False."""
    data = {**SAMPLE_HEALTHCHECK, "sss_status": False}
    with patch("status.get_healthcheck", new=AsyncMock(return_value=data)):
        response = await test_client.get("/prtg")
    assert response.status_code == 200
    body = await response.get_json()
    assert body["prtg"]["error"] == 1
    channels = {ch["channel"]: ch for ch in body["prtg"]["result"]}
    assert channels["SSS status"].get("error") == 1


# --- /api/<source>/latest ---


@pytest.mark.asyncio
async def test_api_source_latest_success(test_client):
    """Test /api/<source>/latest returns a success button with a naturaltime string."""
    json_data = {"objects": [{"seen": "2026-01-01T00:00:00+08:00", "age_minutes": 5}]}
    with patch("status.get_session", return_value=make_mock_client(json_data=json_data)):
        response = await test_client.get("/api/all-sources/latest")
    assert response.status_code == 200
    assert b"button-success" in response.response.data


@pytest.mark.asyncio
async def test_api_source_latest_error(test_client):
    """Test /api/<source>/latest returns an error button on HTTP failure."""
    with patch("status.get_session", return_value=make_mock_client(raise_error=True)):
        response = await test_client.get("/api/all-sources/latest")
    assert response.status_code == 200
    assert b"button-error" in response.response.data


@pytest.mark.asyncio
async def test_api_source_latest_invalid_source(test_client):
    """Test /api/<source>/latest returns an error button for an unknown source name."""
    with patch("status.get_session", return_value=make_mock_client()):
        response = await test_client.get("/api/unknown-source/latest")
    assert response.status_code == 200
    assert b"button-error" in response.response.data


# --- /api/<source>/loggedpoint-rate ---


@pytest.mark.asyncio
async def test_api_source_loggedpoint_rate_success(test_client):
    """Test /api/<source>/loggedpoint-rate returns a rate button."""
    json_data = {"logged_point_count": 50, "minutes": 5}
    with patch("status.get_session", return_value=make_mock_client(json_data=json_data)):
        response = await test_client.get("/api/iridium/loggedpoint-rate")
    assert response.status_code == 200
    assert b"points/min" in response.response.data


@pytest.mark.asyncio
async def test_api_source_loggedpoint_rate_error(test_client):
    """Test /api/<source>/loggedpoint-rate returns an error button on HTTP failure."""
    with patch("status.get_session", return_value=make_mock_client(raise_error=True)):
        response = await test_client.get("/api/iridium/loggedpoint-rate")
    assert response.status_code == 200
    assert b"button-error" in response.response.data


# --- /api/<source>/delay ---


@pytest.mark.asyncio
async def test_api_source_delay_within_limit(test_client):
    """Test /api/<source>/delay returns a success button when age is within the limit."""
    json_data = {"objects": [{"age_minutes": 5}]}
    with patch("status.get_session", return_value=make_mock_client(json_data=json_data)):
        response = await test_client.get("/api/all-sources/delay")
    assert response.status_code == 200
    assert b"button-success" in response.response.data


@pytest.mark.asyncio
async def test_api_source_delay_exceeded(test_client):
    """Test /api/<source>/delay returns an error button when delay exceeds the maximum."""
    json_data = {"objects": [{"age_minutes": 999}]}
    with patch("status.get_session", return_value=make_mock_client(json_data=json_data)):
        response = await test_client.get("/api/all-sources/delay")
    assert response.status_code == 200
    assert b"button-error" in response.response.data


@pytest.mark.asyncio
async def test_api_source_delay_error(test_client):
    """Test /api/<source>/delay returns an error button on HTTP failure."""
    with patch("status.get_session", return_value=make_mock_client(raise_error=True)):
        response = await test_client.get("/api/all-sources/delay")
    assert response.status_code == 200
    assert b"button-error" in response.response.data


# --- /api/kmi-wmts-layers ---


@pytest.mark.asyncio
async def test_api_kmi_wmts_layers_success(test_client):
    """Test /api/kmi-wmts-layers parses WMTS XML and returns a layer count button."""
    with patch("status.get_session", return_value=make_mock_client(content=KMI_WMTS_XML)):
        response = await test_client.get("/api/kmi-wmts-layers")
    assert response.status_code == 200
    assert b"layers" in response.response.data


@pytest.mark.asyncio
async def test_api_kmi_wmts_layers_error(test_client):
    """Test /api/kmi-wmts-layers returns an error button on HTTP failure."""
    with patch("status.get_session", return_value=make_mock_client(raise_error=True)):
        response = await test_client.get("/api/kmi-wmts-layers")
    assert response.status_code == 200
    assert b"button-error" in response.response.data


# --- /api/csw-layers ---


@pytest.mark.asyncio
async def test_api_csw_layers_success(test_client):
    """Test /api/csw-layers returns a button with the catalogue layer count."""
    json_data = [{"id": 1}, {"id": 2}, {"id": 3}]
    with patch("status.get_session", return_value=make_mock_client(json_data=json_data)):
        response = await test_client.get("/api/csw-layers")
    assert response.status_code == 200
    assert b"3 layers" in response.response.data


@pytest.mark.asyncio
async def test_api_csw_layers_error(test_client):
    """Test /api/csw-layers returns an error button on HTTP failure."""
    with patch("status.get_session", return_value=make_mock_client(raise_error=True)):
        response = await test_client.get("/api/csw-layers")
    assert response.status_code == 200
    assert b"button-error" in response.response.data


# --- /api/bfrs-status ---


@pytest.mark.asyncio
async def test_api_bfrs_status_success(test_client):
    """Test /api/bfrs-status returns a success button when the endpoint responds."""
    with patch("status.get_session", return_value=make_mock_client()):
        response = await test_client.get("/api/bfrs-status")
    assert response.status_code == 200
    assert b"button-success" in response.response.data


@pytest.mark.asyncio
async def test_api_bfrs_status_error(test_client):
    """Test /api/bfrs-status returns an error button on HTTP failure."""
    with patch("status.get_session", return_value=make_mock_client(raise_error=True)):
        response = await test_client.get("/api/bfrs-status")
    assert response.status_code == 200
    assert b"button-error" in response.response.data


# --- /api/auth2-status ---


@pytest.mark.asyncio
async def test_api_auth2_status_success(test_client):
    """Test /api/auth2-status returns a success button when the endpoint responds."""
    with patch("status.get_session", return_value=make_mock_client()):
        response = await test_client.get("/api/auth2-status")
    assert response.status_code == 200
    assert b"button-success" in response.response.data


@pytest.mark.asyncio
async def test_api_auth2_status_error(test_client):
    """Test /api/auth2-status returns an error button on HTTP failure."""
    with patch("status.get_session", return_value=make_mock_client(raise_error=True)):
        response = await test_client.get("/api/auth2-status")
    assert response.status_code == 200
    assert b"button-error" in response.response.data


# --- /api/sss-status ---


@pytest.mark.asyncio
async def test_api_sss_status_success(test_client):
    """Test /api/sss-status returns a success button when the endpoint responds."""
    with patch("status.get_session", return_value=make_mock_client()):
        response = await test_client.get("/api/sss-status")
    assert response.status_code == 200
    assert b"button-success" in response.response.data


@pytest.mark.asyncio
async def test_api_sss_status_error(test_client):
    """Test /api/sss-status returns an error button on HTTP failure."""
    with patch("status.get_session", return_value=make_mock_client(raise_error=True)):
        response = await test_client.get("/api/sss-status")
    assert response.status_code == 200
    assert b"button-error" in response.response.data


# --- /api/todays-burns ---


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


@pytest.mark.asyncio
async def test_todays_burns_error(test_client):
    """Test the /api/todays-burns endpoint returns an error button on HTTP failure."""
    with patch("status.get_anonymous_session", return_value=make_mock_client(raise_error=True)):
        response = await test_client.get("/api/todays-burns")
    assert response.status_code == 200
    assert b"button-error" in response.response.data


# --- /api/kb/<kb_layer> ---


@pytest.mark.asyncio
async def test_api_kb_layer_success(test_client):
    """Test /api/kb/<kb_layer> returns a success button when the layer responds."""
    with patch("status.get_kb_layer", new=AsyncMock(return_value=True)):
        response = await test_client.get("/api/kb/dbca-incident-mapping-polygons")
    assert response.status_code == 200
    assert b"button-success" in response.response.data


@pytest.mark.asyncio
async def test_api_kb_layer_error(test_client):
    """Test /api/kb/<kb_layer> returns an error button when the layer does not respond."""
    with patch("status.get_kb_layer", new=AsyncMock(return_value=False)):
        response = await test_client.get("/api/kb/dbca-incident-mapping-polygons")
    assert response.status_code == 200
    assert b"button-error" in response.response.data


# --- /api/kmi/<kmi_layer> ---


@pytest.mark.asyncio
async def test_api_kmi_layer_success(test_client):
    """Test /api/kmi/<kmi_layer> returns a success button when the layer responds."""
    with patch("status.get_kmi_layer", new=AsyncMock(return_value=True)):
        response = await test_client.get("/api/kmi/cog-basemap")
    assert response.status_code == 200
    assert b"button-success" in response.response.data


@pytest.mark.asyncio
async def test_api_kmi_layer_error(test_client):
    """Test /api/kmi/<kmi_layer> returns an error button when the layer does not respond."""
    with patch("status.get_kmi_layer", new=AsyncMock(return_value=False)):
        response = await test_client.get("/api/kmi/cog-basemap")
    assert response.status_code == 200
    assert b"button-error" in response.response.data
