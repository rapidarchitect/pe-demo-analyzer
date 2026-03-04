import json
import pytest
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient, ASGITransport
from backend.main import app
from backend.models import (
    CompanyVitals, DealClassification, BuyoutMetrics, DealAnalysis
)


@pytest.fixture
def mock_analysis():
    return DealAnalysis(
        vitals=CompanyVitals(name="Acme Corp", geography="Germany"),
        classification=DealClassification(
            category="buyout", confidence=0.91, reasoning="Mature profitable"
        ),
        metrics=BuyoutMetrics(revenue="€42M", ebitda="€8M"),
    )


@pytest.mark.asyncio
async def test_health_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "provider" in data


@pytest.mark.asyncio
async def test_analyze_endpoint_streams_sse(mock_analysis):
    from io import BytesIO
    fake_file_content = b"Revenue EUR 42M EBITDA EUR 8M leveraged buyout"

    with patch("backend.main.extract_uploads_to_markdown", new_callable=AsyncMock) as mock_extract, \
         patch("backend.main.run_pipeline", new_callable=AsyncMock) as mock_pipeline:

        mock_extract.return_value = "Revenue EUR 42M"
        mock_pipeline.return_value = mock_analysis

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/analyze",
                files={"files": ("test.txt", BytesIO(fake_file_content), "text/plain")},
            )

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]

    # Parse SSE events from response body
    body = response.text
    events = [line for line in body.split("\n") if line.startswith("data:")]
    assert len(events) >= 4  # extracting, classifying, extracting_metrics, result

    # Last event should be the result
    last_event = json.loads(events[-1].removeprefix("data: "))
    assert last_event["type"] == "result"
    assert last_event["data"]["vitals"]["name"] == "Acme Corp"
    assert last_event["data"]["classification"]["category"] == "buyout"
