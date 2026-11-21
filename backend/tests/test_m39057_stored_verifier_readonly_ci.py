"""M39057 offline unit tests; never opens a real PostgreSQL connection."""
from contextlib import nullcontext
from pathlib import Path

import pytest

from backend.scripts import frfinance_m39057_stored_verifier_readonly as m


class FakeResult:
    def fetchone(self):
        return (m.DB, m.ROLE, m.ROLE, "127.0.0.1", 5433, 180006, "on")


class FakeConnection:
    def __init__(self):
        self.calls = []

    def transaction(self):
        return nullcontext()

    def execute(self, query):
        self.calls.append(query)
        return FakeResult()


def test_correct_db_only_readonly():
    c = FakeConnection()
    m.verify_readonly_connection(c)
    assert c.calls[0] == "SET TRANSACTION READ ONLY"
    assert all(x.startswith("SELECT ") or x == "SET TRANSACTION READ ONLY" for x in c.calls)


@pytest.mark.parametrize("user,port,db", [
    ("frc_ai_verifier", 5432, m.DB),
    ("frc22_owner", 5433, m.DB),
    ("frc_ai_verifier", 5433, "frcaixinha_2_2_dev"),
])
def test_refuse_cross_database_or_role(user, port, db):
    with pytest.raises(m.GuardBlocked):
        m.check_target(f"postgresql://{user}:abc@127.0.0.1:{port}/{db}", m.ROLE)


def test_accept_canonical_urls():
    m.check_target(f"postgresql://{m.ROLE}:some%40secret@127.0.0.1:5433/{m.DB}", m.ROLE)
    m.check_target(f"postgresql://{m.AUTH_ROLE}:secret@127.0.0.1:5433/{m.DB}", m.AUTH_ROLE)


@pytest.mark.parametrize("url", [
    "postgresql://frc_ai_verifier:secret@127.0.0.1:5433/frcaixinha_aistudio_dev?sslmode=disable",
    "postgresql://frc_ai_verifier@127.0.0.1:5433/frcaixinha_aistudio_dev",
    "postgresql://frc_ai_verifier:secret@localhost:5433/frcaixinha_aistudio_dev",
    "postgresql://frc_ai_verifier:secret@127.0.0.1:5433/frcaixinha_aistudio_dev#fragment",
])
def test_refuse_unexpected_url(url):
    with pytest.raises(m.GuardBlocked):
        m.check_target(url, m.ROLE)


def test_noncanonical_config_never_read(tmp_path):
    f = tmp_path / "api.env"
    f.write_text("AUTH_VERIFIER_DATABASE_URL=dummy\n")
    with pytest.raises(m.GuardBlocked, match="NONCANONICAL"):
        m.read_configured_urls(f)


def test_no_password_or_mutation_output_in_source():
    source = (Path(__file__).resolve().parents[1] / "scripts" /
              "frfinance_m39057_stored_verifier_readonly.py").read_text()
    assert "verify_original()" in source
    assert "SET TRANSACTION READ ONLY" in source
    assert "default_transaction_read_only=on" in source
    assert "AUTH_VERIFIER_DATABASE_URL" in source
    for token in ("print(urls)", "print(url)", "print(password)",
                  "ALTER ROLE ", "INSERT INTO ", "UPDATE public.",
                  "CREATE ROLE ", "GRANT ", "os.system(", "subprocess.Popen("):
        assert token not in source
