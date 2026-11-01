"""Contrato de conexão do Android debug com FastAPI local (sem banco real)."""
import os
import subprocess
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app

ROOT = Path(__file__).resolve().parents[2]

def test_health_is_reachable_without_secrets():
    with TestClient(app) as client:
        result = client.get('/api/health')
        assert result.status_code == 200
        assert result.json()['framework'] == 'FastAPI (Python)'

def test_ready_fails_closed_without_database():
    with TestClient(app) as client:
        result = client.get('/api/health/ready')
        assert result.status_code == 503

def test_local_webview_origin_is_opt_in_only():
    code = """
from fastapi.testclient import TestClient
from app.main import app
with TestClient(app) as client:
    headers = {'Origin':'http://localhost','Access-Control-Request-Method':'GET'}
    r=client.options('/api/v1/auth/status',headers=headers)
    assert r.status_code == 200, r.text
    assert r.headers.get('access-control-allow-origin') == 'http://localhost'
    headers['Origin']='https://untrusted.example'
    r=client.options('/api/v1/auth/status',headers=headers)
    assert r.headers.get('access-control-allow-origin') is None
"""
    env = os.environ.copy()
    env.update({'FRCAIXINHA_TERMUX_LOCAL_API': '1', 'ENVIRONMENT': 'homologation'})
    env.pop('APP_URL', None)
    result = subprocess.run([os.sys.executable, '-c', code], env=env, cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr

def test_production_rejects_local_webview_origin():
    code = """
from fastapi.testclient import TestClient
from app.main import app
r=TestClient(app).options('/api/v1/auth/status',headers={'Origin':'http://localhost','Access-Control-Request-Method':'GET'})
assert r.headers.get('access-control-allow-origin') is None
"""
    env = os.environ.copy()
    env.update({'FRCAIXINHA_TERMUX_LOCAL_API': '1', 'ENVIRONMENT': 'production'})
    env.pop('APP_URL', None)
    result = subprocess.run([os.sys.executable, '-c', code], env=env, cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
