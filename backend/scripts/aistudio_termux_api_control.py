#!/usr/bin/env python3
"""AI Studio Termux-only FastAPI start|stop|restart|status (no DB migrations)."""
from __future__ import annotations
import json, os, re, shlex, signal, stat, subprocess, sys, time
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

ROOT=Path.home()/"frcaixinha-aistudio-mobile"
ENVFILE=Path.home()/".config/frcaixinha-aistudio-mobile/api.env"
RUNDIR=Path.home()/".cache/frcaixinha-aistudio"
PIDFILE=RUNDIR/"fastapi-notifications.pid"
LOG=RUNDIR/"fastapi-notifications.log"
BRANCH="atualizacao-ai-studio-9b46a63187"

def fail(reason):
 print("BLOQUEADO: "+reason,file=sys.stderr)
 raise SystemExit(2)

def git(*args):
 return subprocess.check_output(["git","-C",str(ROOT),*args],text=True).strip()

def is_owned_uvicorn(pid):
 try:
  if pid<=0 or not Path(f"/proc/{pid}").is_dir():return False
  statinfo=Path(f"/proc/{pid}").stat()
  if statinfo.st_uid!=os.getuid():return False
  if Path(f"/proc/{pid}/cwd").resolve()!=(ROOT/"backend").resolve():return False
  raw=Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0",b" ")
  return b"uvicorn" in raw and b"app.main:app" in raw
 except (OSError,ValueError,PermissionError):
  return False

def load_env():
 if ENVFILE.is_symlink() or not ENVFILE.is_file() or ENVFILE.parent.is_symlink():
  fail("api.env privado ausente; configure o verificador com o script local")
 st=ENVFILE.stat()
 if st.st_uid!=os.getuid() or stat.S_IMODE(st.st_mode)!=0o600:
  fail("api.env deve pertencer ao usuario e ser chmod 600")
 values={}
 for line in ENVFILE.read_text().splitlines():
  if not line.strip() or line.startswith("#"):continue
  match=re.fullmatch(r"([A-Z_][A-Z0-9_]*)=(.*)",line)
  if not match:fail("api.env possui linha nao permitida")
  name,encoded=match.groups()
  if name in values:fail("variavel duplicada em api.env")
  parts=shlex.split(encoded)
  if len(parts)!=1:fail("valor invalido no api.env: "+name)
  values[name]=parts[0]
 for key in ("DATABASE_URL","AUTH_DATABASE_URL","AUTH_VERIFIER_DATABASE_URL"):
  url=urlparse(values.get(key,""))
  expected={"DATABASE_URL":"frc_ai_app","AUTH_DATABASE_URL":"frc_ai_auth",
            "AUTH_VERIFIER_DATABASE_URL":"frc_ai_verifier"}[key]
  if not (url.scheme=="postgresql" and url.username==expected
    and url.hostname=="127.0.0.1" and url.port==5433
    and url.path=="/frcaixinha_aistudio_dev"):
   fail("DSN nao corresponde ao banco e papel AI Studio: "+key)
 if (values.get("FRCAIXINHA_TEST_AUTH")!="1"
     or values.get("FRCAIXINHA_TERMUX_LOCAL_API")!="1"
     or values.get("AI_STUDIO_IN_APP_NOTIFICATIONS")!="YES"
     or values.get("ENVIRONMENT")=="production"
     or len(values.get("IN_APP_CURSOR_HMAC_KEY","").encode())<32):
  fail("configuracao de autenticacao/avisos locais incompleta")
 return {**os.environ,**values}

def stop():
 if PIDFILE.is_file() and not PIDFILE.is_symlink():
  raw=PIDFILE.read_text().strip()
 else:
  raw=os.environ.get("AI_STUDIO_OLD_FASTAPI_PID","")
 if not raw:print("FASTAPI_STOP=NO_KNOWN_PID");return
 if not raw.isdigit():fail("PID invalido")
 pid=int(raw)
 try:os.kill(pid,0)
 except ProcessLookupError:
  PIDFILE.unlink(missing_ok=True);print("FASTAPI_STOP=ALREADY_STOPPED");return
 if not is_owned_uvicorn(pid):fail("PID nao pertence ao backend AI Studio esperado")
 os.kill(pid,signal.SIGTERM)
 for _ in range(20):
  time.sleep(0.5)
  try:os.kill(pid,0)
  except ProcessLookupError:
   PIDFILE.unlink(missing_ok=True);print("FASTAPI_STOP=PASS");return
 fail("FastAPI anterior nao encerrou; nao iniciar segundo processo")

def start():
 env=load_env()
 if subprocess.run(["pg_isready","-q","-h","127.0.0.1","-p","5433"]).returncode:
  fail("PostgreSQL local 5433 indisponivel")
 try:
  with urlopen("http://127.0.0.1:8000/api/health",timeout=2):
   fail("porta 8000 ocupada por API existente; use restart somente apos verificar PID")
 except OSError:pass
 with LOG.open("ab") as out:
  process=subprocess.Popen(
   [sys.executable,"-m","uvicorn","app.main:app","--host","127.0.0.1",
    "--port","8000","--no-access-log"],
   cwd=ROOT/"backend",env=env,stdin=subprocess.DEVNULL,
   stdout=out,stderr=subprocess.STDOUT,start_new_session=True)
 PIDFILE.write_text(str(process.pid)+"\n")
 os.chmod(PIDFILE,0o600)
 for _ in range(35):
  if process.poll() is not None:break
  try:
   with urlopen("http://127.0.0.1:8000/api/health/features/m19000",timeout=3) as res:
    data=json.load(res)
   if (data.get("contract")=="AI_STUDIO_M19000_LOCAL_IN_APP_NOTIFICATIONS_V1"
    and data.get("local_notification_flag_configured") is True
    and data.get("local_inbox_schema_verified") is True
    and data.get("local_in_app_ready") is True
    and all(data.get(k) is False for k in ("external_email_active",
     "external_push_active","external_whatsapp_active","real_payments_enabled",
     "bank_reconciled","payout_authorized"))):
    print("FASTAPI_PID="+str(process.pid))
    print("M19000_LOCAL_INBOX=READY")
    print("EXTERNAL_SEND=OFF FINANCIAL_EFFECT=OFF")
    return
  except (OSError,ValueError,KeyError):pass
  time.sleep(1)
 if process.poll() is None and is_owned_uvicorn(process.pid):
  process.terminate()
 PIDFILE.unlink(missing_ok=True)
 fail("FastAPI nao confirmou inbox 031; verifique log privado "+str(LOG))

def main():
 mode=sys.argv[1] if len(sys.argv)>1 else "status"
 if mode not in ("start","stop","restart","status"):fail("uso start|stop|restart|status")
 if not ROOT.is_dir():fail("clone AI Studio ausente")
 expected=os.getenv("AI_STUDIO_APPROVED_SHA","")
 if not re.fullmatch("[a-f0-9]{40}",expected):fail("AI_STUDIO_APPROVED_SHA obrigatorio")
 try:
  if (git("branch","--show-current")!=BRANCH or git("rev-parse","HEAD")!=expected
   or git("status","--porcelain","--untracked-files=no")):
   fail("Git local divergente; nenhum processo iniciado/encerrado")
 except (OSError,subprocess.CalledProcessError):fail("Git local indisponivel")
 RUNDIR.mkdir(mode=0o700,parents=True,exist_ok=True)
 os.chmod(RUNDIR,0o700)
 if mode=="status":
  if PIDFILE.is_file() and not PIDFILE.is_symlink():
   raw=PIDFILE.read_text().strip()
   print("FASTAPI_PID="+raw if raw.isdigit() and is_owned_uvicorn(int(raw)) else "FASTAPI=NOT_RUNNING")
  else:print("FASTAPI=NOT_MANAGED")
 elif mode=="stop":stop()
 elif mode=="start":start()
 else:stop();start()

if __name__=="__main__":main()
