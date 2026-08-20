import pytest
from httpx import AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_connector_capabilities(client: AsyncClient):
    # Fetch capabilities
    response = await client.get("/api/v1/workflow/capabilities")
    assert response.status_code == 200
    
    data = response.json()
    
    # Verify workable capabilities
    assert "workable" in data
    workable = data["workable"]
    assert workable["discovery"] is True
    assert workable["application_preparation"] is True
    assert workable["submission"] is False
    assert workable["status_monitoring"] is False
    
    # Verify greenhouse capabilities
    assert "greenhouse" in data
    greenhouse = data["greenhouse"]
    assert greenhouse["discovery"] is True
    assert greenhouse["application_preparation"] is True
    assert greenhouse["submission"] is False
    assert greenhouse["status_monitoring"] is False
