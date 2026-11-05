#!/usr/bin/env python3
"""Add only two notification keys to an existing private local api.env."""
from pathlib import Path
import os,re,shlex,secrets,stat,subprocess,tempfile,sys
from urllib.parse import urlparse
ROOT=Path.home()/"frcaixinha-aistudio-mobile"
BASE=Path.home()/".config/frcaixinha-aistudio-mobile"
ENV=BASE/"api.env"

def fail(msg):
 print("BLOQUEADO: "+msg,file=sys.stderr)
 return 2

def main():
 sha=os.getenv("AI_STUDIO_APPROVED_SHA","")
 if not re.fullmatch("[a-f0-9]{40}",sha):return fail("informe SHA40 aprovado")
 proc=subprocess.run(["git","-C",str(ROOT),"rev-parse","HEAD"],capture_output=True,text=True)
 if proc.returncode or proc.stdout.strip()!=sha:return fail("commit nao aprovado")
 if ENV.is_symlink() or BASE.is_symlink() or not ENV.is_file():
  return fail("api.env ausente; use aistudio_local_api_setup.py")
 st=ENV.stat()
 if st.st_uid!=os.getuid() or stat.S_IMODE(st.st_mode)!=0o600:return fail("api.env sem permissao 0600")
 old=ENV.read_text(encoding="utf-8")
 entries={}
 for line in old.splitlines():
  m=re.fullmatch(r"([A-Z_][A-Z0-9_]*)=(.*)",line)
  if m:
   if m[1] in entries:return fail("variavel duplicada")
   entries[m[1]]=m[2]
 for key in ("DATABASE_URL","AUTH_DATABASE_URL","AUTH_VERIFIER_DATABASE_URL",
             "FRCAIXINHA_TEST_AUTH","FRCAIXINHA_TERMUX_LOCAL_API"):
  if key not in entries:return fail("configuracao incompleta: "+key)
 u=urlparse(shlex.split(entries["DATABASE_URL"])[0])
 if (u.hostname!="127.0.0.1" or u.port!=5433 or u.username!="frc_ai_app"
    or u.path!="/frcaixinha_aistudio_dev"):
  return fail("DATABASE_URL nao corresponde ao banco AI Studio")
 if "AI_STUDIO_IN_APP_NOTIFICATIONS" in entries:
  if shlex.split(entries["AI_STUDIO_IN_APP_NOTIFICATIONS"])!=["YES"]:
   return fail("flag de notificacoes existente diverge")
 if "IN_APP_CURSOR_HMAC_KEY" in entries:
  if len(shlex.split(entries["IN_APP_CURSOR_HMAC_KEY"])[0])<32:
   return fail("chave de cursor existente insuficiente")
 missing=[]
 if "AI_STUDIO_IN_APP_NOTIFICATIONS" not in entries:
  missing.append("AI_STUDIO_IN_APP_NOTIFICATIONS=YES")
 if "IN_APP_CURSOR_HMAC_KEY" not in entries:
  missing.append("IN_APP_CURSOR_HMAC_KEY="+shlex.quote(secrets.token_urlsafe(48)))
 if not missing:
  print("INBOX_API_ENV=ALREADY_READY");return 0
 if input("Digite ATIVAR_AVISOS_INTERNOS_AI_STUDIO: ").strip()!="ATIVAR_AVISOS_INTERNOS_AI_STUDIO":
  return fail("sem autorizacao")
 tmp=None
 try:
  with tempfile.NamedTemporaryFile(mode="w",encoding="utf-8",dir=BASE,
       prefix=".api-env-notifications-",delete=False) as fh:
   tmp=Path(fh.name);os.fchmod(fh.fileno(),0o600)
   fh.write(old.rstrip("\n")+"\n"+"\n".join(missing)+"\n")
   fh.flush();os.fsync(fh.fileno())
  os.replace(tmp,ENV)
 except OSError:
  if tmp is not None:tmp.unlink(missing_ok=True)
  return fail("gravacao do arquivo privado falhou")
 print("INBOX_API_ENV=READY_0600; nenhum segredo exibido")
 return 0
if __name__=="__main__":raise SystemExit(main())
