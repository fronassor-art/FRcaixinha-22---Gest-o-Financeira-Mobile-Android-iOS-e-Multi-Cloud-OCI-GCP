#!/usr/bin/env python3
"""Historical fixed-price development seed permanently retired.

Do not create policies or contributions from bootstrap defaults.
Every new cycle must use authenticated tenant-admin opening M044 with
an explicitly selected per-member/per-quota amount >= BRL 150.00.
"""
def main()->int:
    print("BLOQUEADO: SEED_LEGADO_DESATIVADO. Abertura exige escolha autenticada pelo administrador.")
    print("CICLO_COTA_MINIMO_CENTAVOS=15000")
    print("DATABASE_WRITES=NONE")
    return 2

if __name__=="__main__":
    raise SystemExit(main())
