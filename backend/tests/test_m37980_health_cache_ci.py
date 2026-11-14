"""M37980: the anonymous API health contract is never cached after deploy."""
from fastapi.testclient import TestClient
from app.main import app

def test_health_header_and_document_shape_are_noncached():
    with TestClient(app) as client:
        response=client.get("/api/health")
        assert response.status_code==200
        body=response.json()
        assert body["status"]=="ONLINE"
        assert body["app"]=="FR Finance"
        assert body["framework"]=="FastAPI (Python)"
        assert type(body["database_configured"]) is bool
        assert response.headers["Cache-Control"]=="no-store"
        assert response.headers["Pragma"]=="no-cache"
        assert response.headers["X-Content-Type-Options"]=="nosniff"

def test_health_unsafe_method_does_not_mutate():
    with TestClient(app) as client:
        result=client.post("/api/health",json={"admin":True})
        assert result.status_code==405
        assert result.headers["Cache-Control"]=="no-store"
