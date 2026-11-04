from pathlib import Path
import subprocess
BASE=Path(__file__).resolve().parents[2] / "public/assets/aistudio"
FILES=["FRcaixinha_2.2___Caderno_Mestre_LIMPO___147_cl_usulas_94d2a15c.pdf","FRcaixinha_2.2___Contrato_T_cnico_Mestre_ORIGINAL_LIMPO_7b28d5d5.pdf"]
for name in FILES:
  pages=subprocess.check_output(["pdftotext","-layout",str(BASE/name),"-"],text=True).split("\f")
  print("DOCUMENT",name,"PAGES",len(pages))
  for number,page in enumerate(pages,1):
    for line in page.splitlines():
      low=line.casefold()
      if any(x in low for x in ["inadimpl","volunt","cancel","desist","mora","bloque","rateio","lucro","multa"]):
        print("CLAUSE_PAGE",number,"TEXT",line.strip()[:260])
