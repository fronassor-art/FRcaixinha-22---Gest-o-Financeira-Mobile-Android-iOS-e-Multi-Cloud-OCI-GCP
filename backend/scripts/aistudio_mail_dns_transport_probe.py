#!/usr/bin/env python3
"""FR Finance M38450–M38489: explicit, redacted public DNS connectivity probe.

SYSTEM uses the DNS resolver as configured in this Python environment.
CLOUDFLARE / GOOGLE are OPTIONAL, require a *distinct* authorization token
and reveal only the fixed public domain frfinance.com.br to those public DNS
operators. Does not change /etc/resolv.conf, Android DNS, OCI, PostgreSQL,
SMTP or Brevo. Does not output addresses or any TXT/DKIM/Brevo-code values.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
sys.path.insert(0,str(HERE.parent))

from app.mail_dns_transport_readonly import diagnose_dns_transport, is_transport_complete
from aistudio_mail_dns_readonly import _local_preflight

PUBLIC_DNS_IP = {"CLOUDFLARE":"1.1.1.1","GOOGLE":"8.8.8.8"}


def _resolver_factory(mode: str):
    import dns.resolver
    # A Termux / Debian PRoot system may have no configured nameservers.
    # Do not silently fall back to any third-party resolver.
    resolver=dns.resolver.Resolver(configure=(mode=="SYSTEM"))
    if mode!="SYSTEM":
        resolver.nameservers=[PUBLIC_DNS_IP[mode]]
    resolver.timeout=2.0
    resolver.lifetime=4.0
    return resolver


def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser(
        description="FR Finance public DNS transport status without raw TXT contents.",
    )
    parser.add_argument("mode",nargs="?",choices=("offline","system","cloudflare","google"),
                        default="offline")
    parser.add_argument("authorization",nargs="?")
    args=parser.parse_args(argv)

    if args.mode=="offline":
        if args.authorization is not None:
            print("M38489_PROBE=BLOCKED_AUTHORIZATION")
            return 2
        print("=== FR FINANCE M38450-M38489 DNS TRANSPORT ===")
        print("M38489_MODE=OFFLINE_NO_NETWORK")
        print("M38489_SYSTEM_DNS=NOT_QUERIED")
        print("M38489_ROOT_TXT=NOT_QUERIED")
        print("M38489_DMARC_TXT=NOT_QUERIED")
        print("M38489_CLOUD_MUTATIONS=NONE")
        print("M38489_EMAIL_REAL=OFF")
        print("M38489_PIX_REAL=OFF")
        print("M38489_PRODUCTION=BLOCKED")
        return 0

    required=("AUTHORIZE_PUBLIC_MAIL_DNS_READ_ONLY" if args.mode=="system"
              else "AUTHORIZE_THIRD_PARTY_PUBLIC_DNS_READ_ONLY")
    if args.authorization!=required:
        print("M38489_PROBE=BLOCKED_OPERATOR_AUTHORIZATION_REQUIRED")
        return 2

    # This is public-only domain metadata: no password, token, private email
    # or DNS record contents are read. Reuse the proven local preflight.
    preflight=_local_preflight()
    if preflight!="READY_FOR_EXPLICIT_PUBLIC_DNS_READ":
        print("M38489_PROBE=BLOCKED_LOCAL_PREFLIGHT")
        print("M38489_PREFLIGHT="+preflight)
        print("M38489_NETWORK_QUERIES=NONE")
        print("M38489_EMAIL_REAL=OFF")
        print("M38489_PRODUCTION=BLOCKED")
        return 2

    mode=args.mode.upper()
    report=diagnose_dns_transport(mode, _resolver_factory)
    print("=== FR FINANCE M38489 DNS PUBLIC TRANSPORT READ ONLY ===")
    print("M38489_RESOLVER="+report.mode)
    print("M38489_THIRD_PARTY_DNS="+str(report.third_party_resolver_selected).upper())
    print("M38489_RESOLVER_STATUS="+report.resolver_status)
    print("M38489_ROOT_TXT="+report.root_txt_status)
    print("M38489_DMARC_TXT="+report.dmarc_txt_status)
    print("M38489_QUERIES_ATTEMPTED="+str(report.queries_requested))
    print("M38489_TRANSPORT_COMPLETED="+str(is_transport_complete(report)).upper())
    print("M38489_DNS_TXT_VALUES_PRINTED=FALSE")
    print("M38489_BREVO_DOMAIN_AUTH=NOT_ATTESTED")
    print("M38489_SMTP_DELIVERY=NOT_ATTESTED")
    print("M38489_CLOUD_MUTATIONS=NONE")
    print("M38489_DATABASE_MUTATIONS=NONE")
    print("M38489_EMAIL_REAL=OFF")
    print("M38489_PIX_REAL=OFF")
    print("M38489_REAL_ACTIVATION=OFF")
    print("M38489_PRODUCTION=BLOCKED")
    return 0 if is_transport_complete(report) else 2


if __name__=="__main__":
    raise SystemExit(main())
