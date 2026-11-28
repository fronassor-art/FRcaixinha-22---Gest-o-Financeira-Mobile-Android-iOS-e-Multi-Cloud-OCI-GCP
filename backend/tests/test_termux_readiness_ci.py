"""Prontidão com dois papéis PostgreSQL criados no serviço isolado do CI."""
import os
import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_api_ready_for_test_auth_with_disposable_postgres():
    # This integration reaches the real /ready route and its disposable
    # PostgreSQL fixture. Never touch the original Termux DB in bulk pytest.
    # CI runners without an explicitly isolated database also skip safely.
    if (os.environ.get('GITHUB_ACTIONS') != 'true'
            or os.environ.get('FRCAIXINHA_CI_ISOLATED') != '1'
            or os.environ.get('PGDATABASE') == 'frcaixinha_aistudio_dev'
            or os.environ.get('PGPORT') == '5433'):
        pytest.skip('requires GitHub Actions with explicitly isolated disposable PostgreSQL')
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        response = await client.get('/api/health/ready')
    assert response.status_code == 200, response.text
    assert response.json() == {'status': 'READY_FOR_TEST_AUTH', 'scope': 'LOCAL_HOMOLOGATION_ONLY'}
