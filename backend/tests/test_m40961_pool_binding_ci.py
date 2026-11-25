"""M40961: cached pool configuration integrity; no real DB/network."""
import asyncio
from unittest.mock import AsyncMock, Mock
import asyncpg
import pytest
from app import database as db

BASE = "postgresql://frc_ai_app:synthetic@127.0.0.1:5433/frcaixinha_aistudio_dev"
OTHER = "postgresql://frc_ai_app:other-synthetic@127.0.0.1:5433/frcaixinha_aistudio_dev"

@pytest.fixture
def fixture(monkeypatch):
    for key, value in {"ENVIRONMENT":"development",
                       "FRCAIXINHA_TERMUX_LOCAL_API":"1",
                       "PIX_REAL":"OFF","PAGAMENTOS_REAIS":"OFF",
                       "ATIVACAO_REAL":"OFF"}.items():
        monkeypatch.setenv(key,value)
    for key in ("AUTH_DATABASE_URL","AUTH_VERIFIER_DATABASE_URL","DATABASE_URL"):
        monkeypatch.delenv(key,raising=False)
    monkeypatch.setattr(db.settings,"DATABASE_URL",BASE)
    monkeypatch.setattr(db,"_db_pool",None)
    monkeypatch.setattr(db,"_db_pool_binding",None)
    monkeypatch.setattr(db,"_db_pool_lock",asyncio.Lock())
    pool=Mock()
    pool.close=AsyncMock()
    create=AsyncMock(return_value=pool)
    monkeypatch.setattr(asyncpg,"create_pool",create)
    return pool,create

@pytest.mark.asyncio
async def test_concurrent_acquisition_creates_single_pool(fixture):
    pool,create=fixture
    async def create_candidate(**kwargs):
        await asyncio.sleep(0)
        return pool
    create.side_effect=create_candidate
    assert all(x is pool for x in await asyncio.gather(*(db.get_db_pool() for _ in range(12))))
    assert create.await_count==1

@pytest.mark.asyncio
@pytest.mark.parametrize("change",["dsn","environment","auth"])
async def test_changed_valid_config_refuses_cached_pool(fixture,monkeypatch,change):
    pool,create=fixture
    assert await db.get_db_pool() is pool
    if change=="dsn":
        monkeypatch.setattr(db.settings,"DATABASE_URL",OTHER)
    elif change=="environment":
        monkeypatch.setenv("ENVIRONMENT","staging")
    else:
        monkeypatch.setenv("AUTH_DATABASE_URL",BASE.replace("frc_ai_app","frc_ai_auth"))
    with pytest.raises(RuntimeError,match="M40961_FINANCIAL_POOL_CONFIGURATION_CHANGED"):
        await db.get_db_pool()
    assert create.await_count==1
    pool.terminate.assert_not_called()

@pytest.mark.asyncio
async def test_unbound_cached_pool_rejected(fixture,monkeypatch):
    pool,create=fixture
    monkeypatch.setattr(db,"_db_pool",pool)
    with pytest.raises(RuntimeError,match="M40961_FINANCIAL_POOL_CONFIGURATION_CHANGED"):
        await db.get_db_pool()
    create.assert_not_awaited()

@pytest.mark.asyncio
@pytest.mark.parametrize("change",["dsn","production","flag"])
async def test_config_change_during_initialization_never_publishes_pool(fixture,monkeypatch,change):
    pool,create=fixture
    async def open_candidate(**kwargs):
        if change=="dsn":
            monkeypatch.setattr(db.settings,"DATABASE_URL",OTHER)
        elif change=="production":
            monkeypatch.setenv("ENVIRONMENT","production")
        else:
            monkeypatch.setenv("PIX_REAL","ON")
        return pool
    create.side_effect=open_candidate
    with pytest.raises(RuntimeError):
        await db.get_db_pool()
    pool.terminate.assert_called_once_with()
    assert db._db_pool is None and db._db_pool_binding is None

@pytest.mark.asyncio
async def test_close_clears_binding_then_new_configuration_can_open(fixture,monkeypatch):
    pool,create=fixture
    await db.get_db_pool()
    await db.close_db_pool()
    pool.close.assert_awaited_once()
    assert db._db_pool is None and db._db_pool_binding is None
    monkeypatch.setattr(db.settings,"DATABASE_URL",OTHER)
    assert await db.get_db_pool() is pool
    assert create.await_count==2

@pytest.mark.asyncio
async def test_initialization_failure_does_not_publish_binding(fixture):
    pool,create=fixture
    create.side_effect=RuntimeError("synthetic")
    with pytest.raises(RuntimeError,match="synthetic"):
        await db.get_db_pool()
    assert db._db_pool is None and db._db_pool_binding is None
