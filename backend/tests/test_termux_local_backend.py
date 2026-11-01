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


def test_ai_studio_database_guard_requires_dedicated_cluster_and_roles():
    """Testa apenas formato de URLs; jamais conecta ou cria PostgreSQL."""
    checker = ROOT / 'backend/scripts/validate_aistudio_database.py'
    finance = 'postgresql://frc_ai_app:ci-placeholder@127.0.0.1:5433/frcaixinha_aistudio_dev'
    auth = 'postgresql://frc_ai_auth:ci-placeholder@127.0.0.1:5433/frcaixinha_aistudio_dev'

    def invoke(main_url, auth_url):
        env = os.environ.copy()
        env.pop('DATABASE_URL', None)
        env.pop('AUTH_DATABASE_URL', None)
        if main_url:
            env['DATABASE_URL'] = main_url
        if auth_url:
            env['AUTH_DATABASE_URL'] = auth_url
        return subprocess.run(
            [os.sys.executable, str(checker)],
            cwd=ROOT, env=env, capture_output=True, text=True,
        )

    # API ainda sem banco próprio: health permitido; login continua bloqueado.
    assert invoke(None, None).returncode == 0
    # Configuração isolada futura é aceita sem abrir conexão ao servidor.
    assert invoke(finance, auth).returncode == 0

    invalid = [
        (finance, None),
        (None, auth),
        (finance.replace(':5433/', ':5432/'), auth),
        (finance.replace('frcaixinha_aistudio_dev', 'frcaixinha_2_2_dev'), auth),
        (finance.replace('frc_ai_app', 'frc22_owner'), auth),
        (finance.replace('127.0.0.1', '192.168.1.25'), auth),
        (finance, auth.replace('frc_ai_auth', 'frc_ai_app')),
    ]
    for bad_main, bad_auth in invalid:
        result = invoke(bad_main, bad_auth)
        assert result.returncode == 2, (bad_main, result.stdout)
        assert 'BLOQUEADO' in result.stderr
        assert 'ci-placeholder' not in result.stdout + result.stderr
