#!/usr/bin/env python3
"""M38250–M38289: opt-in public sender-domain TXT / CNAME DNS observations.

Requires optional dnspython for LIVE only. DNS queries are limited to the
approved FR Finance sending domain and up to two operator-supplied DKIM
selectors. Never reads email credentials, connects SMTP, sends email or
changes OCI/DNS/DB. Output contains only fixed flags and blocker codes.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
sys.path.insert(0,str(HERE.parent))

from app.mail_dns_readiness_readonly import (
    DkimDnsObservation, MailDnsObservationBlocked, PublicMailDnsSnapshot,
    assess_public_mail_dns,
)
from app.brevo_sender_dns_policy import assess_brevo_public_dns
from aistudio_provider_intake import _default_file, read_file

SENDER_DOMAIN = "frfinance.com.br"
SELECTOR = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\Z")


def _failure() -> MailDnsObservationBlocked:
    return MailDnsObservationBlocked("M38250_PUBLIC_MAIL_DNS_UNAVAILABLE")


def _read_source_domain() -> str:
    public = read_file(_default_file())["public_inputs"]
    sender = public.get("FR_FINANCE_EMAIL_FROM")
    if type(sender) is not str or sender.count("@") != 1:
        raise _failure()
    local, domain = sender.rsplit("@",1)
    if not local or domain != SENDER_DOMAIN:
        raise _failure()
    return domain


def _collect_public_dns(domain: str, selectors: tuple[str,...]) -> PublicMailDnsSnapshot:
    # Import only inside explicit LIVE, never in CI or offline.
    try:
        import dns.exception
        import dns.resolver
        resolver = dns.resolver.Resolver(configure=True)
        resolver.timeout = 2.0
        resolver.lifetime = 5.0
    except Exception:
        raise _failure() from None

    def query(name: str, record_type: str):
        try:
            answers = resolver.resolve(name, record_type, raise_on_no_answer=False)
            if answers.rrset is None:
                return ()
            values = tuple(answers)
            if len(values) > 40:
                raise _failure()
            return values
        except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
            return ()
        except Exception:
            raise _failure() from None

    def txt(name: str) -> tuple[str, ...]:
        rows = query(name,"TXT")
        values = []
        for entry in rows:
            try:
                chunks=entry.strings
                if not chunks or any(type(x) is not bytes for x in chunks):
                    raise _failure()
                value=b"".join(chunks).decode("ascii")
                if not 0<len(value)<=4096:
                    raise _failure()
                values.append(value)
            except Exception:
                raise _failure() from None
        return tuple(values)

    records: list[DkimDnsObservation] = []
    for selector in selectors:
        owner=selector+"._domainkey."+domain
        cnames=query(owner,"CNAME")
        if len(cnames)>1:
            raise _failure()
        if cnames:
            try:
                target=cnames[0].target.to_text(omit_final_dot=True).lower()
            except Exception:
                raise _failure() from None
            records.append(DkimDnsObservation(
                selector=selector,record_kind="CNAME",record_value=target,
            ))
        else:
            dkim_txt=[r for r in txt(owner) if r.lower().startswith("v=dkim1;")]
            if len(dkim_txt)>1:
                raise _failure()
            records.append(DkimDnsObservation(
                selector=selector,
                record_kind="TXT" if dkim_txt else "MISSING",
                record_value=dkim_txt[0] if dkim_txt else None,
            ))

    # Query domain TXT and DMARC after the selector preflight.
    return PublicMailDnsSnapshot(
        sender_domain=domain,
        spf_txt=txt(domain),
        dmarc_txt=txt("_dmarc."+domain),
        dkim=tuple(records),
    )


def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser(
        description="FR Finance e-mail DNS público, somente leitura; sem SMTP.",
    )
    parser.add_argument("action",choices=("offline","live"),nargs="?",default="offline")
    parser.add_argument("approval",nargs="?",default=None)
    parser.add_argument("--selector",action="append",default=[])
    args=parser.parse_args(argv)
    if args.action=="offline":
        if args.approval is not None or args.selector:
            print("M38289_MAIL_DNS=BLOCKED_INVALID_OFFLINE_ARGUMENTS")
            return 2
        print("=== FR FINANCE M38250-M38289 MAIL DNS ===")
        print("M38289_MODE=OFFLINE_NO_DNS_REQUESTS")
        print("M38289_SPF=NOT_QUERIED")
        print("M38289_DMARC=NOT_QUERIED")
        print("M38289_DKIM=NOT_QUERIED")
        print("M38289_REAL_EMAIL=OFF")
        print("M38289_PIX_REAL=OFF")
        print("M38289_PRODUCTION=BLOCKED")
        return 0

    if (
        args.approval!="AUTHORIZE_PUBLIC_MAIL_DNS_READ_ONLY"
        or len(args.selector)>2 or len(set(args.selector))!=len(args.selector)
        or any(type(s) is not str or SELECTOR.fullmatch(s) is None
               for s in args.selector)
    ):
        print("M38289_MAIL_DNS=BLOCKED_OPERATOR_APPROVAL_OR_SELECTOR")
        return 2
    try:
        domain=_read_source_domain()
        snapshot=_collect_public_dns(domain,tuple(args.selector))
        report=assess_public_mail_dns(snapshot)
        brevo=assess_brevo_public_dns(snapshot)
    except Exception:
        # No DNS, intake or provider exception text; fixed reason only.
        print("M38289_MAIL_DNS=BLOCKED_INPUT_OR_DNS_QUERY")
        print("M38289_REAL_EMAIL=OFF")
        print("M38289_PRODUCTION=BLOCKED")
        return 2

    print("=== FR FINANCE M38289 MAIL DNS PUBLIC READ ONLY ===")
    print("M38289_MAIL_DNS=READ_ONLY_OBSERVATION")
    print("M38289_SPF_RECORD="+str(report.spf_record_present).upper())
    print("M38289_SPF_LIMITED="+str(report.spf_policy_limited).upper())
    print("M38289_DMARC_RECORD="+str(report.dmarc_record_present).upper())
    print("M38289_DMARC_POLICY="+report.dmarc_policy)
    print("M38289_DKIM_SELECTORS="+str(report.dkim_selectors_observed))
    print("M38289_DKIM_RECORDS="+str(report.dkim_records_present))
    # The generic legacy policy may flag an absent SPF, p=none or one
    # DKIM TXT even though all are compatible with the Brevo account
    # authentication flow. Print only the provider-specific diagnosis.
    print("M38329_BREVO_CODE_RECORD="+str(brevo.brevo_code_record_observed).upper())
    print("M38329_SPF_OPTIONAL_FOR_SHARED_BREVO=TRUE")
    print("M38329_SPF_STATUS="+brevo.spf_status)
    print("M38329_DMARC_STATUS="+brevo.dmarc_status)
    print("M38329_DMARC_RUA="+str(brevo.dmarc_rua_observed).upper())
    print("M38329_DKIM_MODE="+brevo.dkim_mode)
    print("M38329_DNS_SHAPE_COMPLETE="+str(brevo.public_dns_candidates_complete).upper())
    for blocker in brevo.blockers:
        print("M38329_BLOCKER="+blocker)
    print("M38329_PROVIDER_AUTHENTICATED=NOT_VERIFIED")
    print("M38289_PROVIDER_SENDER=NOT_VERIFIED")
    print("M38289_SMTP_AUTH=NOT_TESTED")
    print("M38289_EMAIL_DELIVERY=NOT_ATTESTED")
    print("M38289_REAL_EMAIL=OFF")
    print("M38289_REAL_ACTIVATION=OFF")
    print("M38289_PIX_REAL=OFF")
    print("M38289_CLOUD_MUTATIONS=NONE")
    print("M38289_DATABASE_MUTATIONS=NONE")
    print("M38289_PRODUCTION=BLOCKED")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
