"""M19100 incremental script must never replay 001-027."""
import subprocess
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]
def test_incremental_installer_is_safe_without_termux():
    p=BASE/"scripts/aistudio_notifications_incremental.sh"
    subprocess.run(["bash","-n",str(p)],check=True)
    r=subprocess.run(["bash",str(p),"audit"],capture_output=True,text=True,timeout=10)
    assert r.returncode!=0 and "BLOQUEADO" in r.stderr
    s=p.read_text()
    for k in ("aistudio_notifications_existing_base_guard.sql","AI_STUDIO_APPROVED_SHA",
              "age --passphrase","--single-transaction","031_notification_inbox_local_sandbox.sql",
              "aistudio_post_migration_roles.sql","M19100_MIGRACAO_031_INCREMENTAL=PASS"):
        assert k in s,k
    assert "AI_STUDIO_APPLY_MIGRATIONS=YES" not in s
    assert '"$root/backend/scripts/aistudio_db_local.sh" apply' not in s
