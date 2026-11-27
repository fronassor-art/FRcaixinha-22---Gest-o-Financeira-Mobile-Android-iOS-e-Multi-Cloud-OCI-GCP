"""Compose actual TypeScript mobile form payloads with existing ASGI/PG18 tests.
Only synthetic secrets on subprocess pipes; no files, logs, shell or network.
"""
import json,os,subprocess
from pathlib import Path
from fastapi.encoders import jsonable_encoder
ROOT=Path(__file__).resolve().parents[2]

def form_request(op,**kw):
    if (os.environ.get("GITHUB_ACTIONS")!="true" or os.environ.get("FRCAIXINHA_CI_ISOLATED")!="1"
        or os.environ.get("PGDATABASE")!="frcaixinha_ci" or os.environ.get("PGPORT")!="5432"
        or any(os.environ.get(k)!="OFF" for k in ("PIX_REAL","PAGAMENTOS_REAIS","ATIVACAO_REAL"))):
        raise RuntimeError("M41440 requires isolated CI")
    result=subprocess.run([str(ROOT/"node_modules/.bin/tsx"),str(ROOT/"src/tests/m41440_onboarding_form_bridge.ts")],
        input=json.dumps(jsonable_encoder(dict(op=op,**kw))),text=True,capture_output=True,timeout=30,cwd=ROOT)
    if result.returncode!=0:
        raise AssertionError("M41440 mobile form rejected")
    request=json.loads(result.stdout)
    assert set(request)=={"path","body"}
    return request

def scope_of(row):
    return dict(userId=row["user_id"],tenantId=row["tenant_id"],role=row["role"])
