-- AI STUDIO M5000/M5100: ORDERS durable reservation + tenant composite integrity.
-- STAGING OCI ONLY; NOT APPLIED; NEVER Termux 5433 or production.
-- Prereqs: M034 M035 M036 M037, dedicated unprivileged financial worker.
BEGIN;

DO $guard$
BEGIN
 IF current_database()<>'frcaixinha_staging'
    OR current_setting('frcaixinha.orders_staging_authorized',true) IS DISTINCT FROM '1'
    OR current_setting('is_superuser')<>'on'
    OR NOT EXISTS (
       SELECT 1 FROM pg_roles
       WHERE rolname='frcaixinha_mp_financial_worker'
         AND NOT rolsuper AND NOT rolbypassrls
    )
    OR to_regclass('public.mp_pix_collection_operations_staging') IS NULL
    OR to_regclass('public.mp_pix_settlement_evidence_staging') IS NULL
    OR to_regclass('public.mp_pix_receipts_staging') IS NULL
    OR to_regclass('public.mp_orders_provider_reads_staging') IS NULL
    OR to_regclass('public.mp_seller_connections_staging') IS NULL
    OR to_regclass('public.contributions') IS NULL
    OR to_regclass('public.loan_installments') IS NULL THEN
   RAISE EXCEPTION 'M038 DENIED: OCI staging + DBA + M034-M037 + role';
 END IF;
END $guard$;

-- M035 used varchar(40) for numeric legacy payments, but Orders PAY IDs are
-- alphanumeric and may be up to 80 characters.
ALTER TABLE public.mp_pix_collection_operations_staging
 ALTER COLUMN provider_payment_id TYPE varchar(80);
ALTER TABLE public.mp_pix_settlement_evidence_staging
 ALTER COLUMN provider_payment_id TYPE varchar(80);
ALTER TABLE public.mp_pix_receipts_staging
 ALTER COLUMN provider_payment_id TYPE varchar(80);

ALTER TABLE public.mp_pix_collection_operations_staging
 ADD CONSTRAINT mp_pix_collection_tenant_operation_uq UNIQUE(tenant_id,operation_id);
ALTER TABLE public.mp_pix_settlement_evidence_staging
 ADD CONSTRAINT mp_pix_settlement_tenant_operation_fk
 FOREIGN KEY(tenant_id,operation_id)
 REFERENCES public.mp_pix_collection_operations_staging(tenant_id,operation_id)
 ON DELETE RESTRICT;
ALTER TABLE public.mp_pix_receipts_staging
 ADD CONSTRAINT mp_pix_receipts_tenant_operation_fk
 FOREIGN KEY(tenant_id,operation_id)
 REFERENCES public.mp_pix_collection_operations_staging(tenant_id,operation_id)
 ON DELETE RESTRICT;
ALTER TABLE public.mp_orders_provider_reads_staging
 ADD CONSTRAINT mp_orders_read_tenant_operation_fk
 FOREIGN KEY(tenant_id,operation_id)
 REFERENCES public.mp_pix_collection_operations_staging(tenant_id,operation_id)
 ON DELETE RESTRICT;

-- The financial worker may reserve only on behalf of its bound seller.
-- It cannot call this RPC with a different session_user or another account.
CREATE OR REPLACE FUNCTION public.mp_orders_staging_reserve(
 p_tenant uuid, p_cycle uuid, p_membership uuid,
 p_obligation uuid, p_kind varchar, p_loan uuid,
 p_amount bigint, p_attempt smallint,
 p_operation varchar, p_reference varchar,
 p_key varchar, p_collector varchar,
 p_terms varchar, p_environment varchar
) RETURNS text
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp AS $fn$
DECLARE current_row public.mp_pix_collection_operations_staging%ROWTYPE;
DECLARE other_operation varchar(64);
BEGIN
 IF current_database()<>'frcaixinha_staging'
    OR session_user<>'frcaixinha_mp_financial_worker'
    OR p_tenant IS NULL OR p_cycle IS NULL
    OR p_membership IS NULL OR p_obligation IS NULL
    OR p_kind IS NULL OR p_kind NOT IN ('CONTRIBUTION','LOAN_INSTALLMENT')
    OR p_amount IS NULL OR p_amount<=0 OR p_amount>999999999999
    OR p_attempt NOT BETWEEN 1 AND 999
    OR p_operation !~ '^P_[0-9a-f]{32}$'
    OR p_reference !~ '^FRC_[0-9a-f]{40}$'
    OR p_key !~ '^pix_[0-9a-f]{40}$'
    OR p_collector !~ '^[0-9]{1,40}$'
    OR p_terms !~ '^[A-Za-z0-9._:-]{8,100}$'
    OR p_environment IS NULL OR p_environment NOT IN ('HOMOLOGACAO','PRODUCAO')
    OR p_environment='PRODUCAO'
    OR (p_kind='LOAN_INSTALLMENT')<>(p_loan IS NOT NULL)
    OR NOT EXISTS (
      SELECT 1 FROM public.mp_seller_connections_staging s
      WHERE s.tenant_id=p_tenant AND s.seller_id=p_collector
        AND s.revoked_at IS NULL
    )
    OR NOT EXISTS(
      SELECT 1 FROM public.memberships m
      WHERE m.id=p_membership AND m.tenant_id=p_tenant AND m.status='ATIVA'
    )
    OR NOT EXISTS(
      SELECT 1 FROM public.cycles c
      WHERE c.id=p_cycle AND c.tenant_id=p_tenant AND c.status='ABERTO'
    ) THEN
   RAISE EXCEPTION 'M038 DENIED: collection account or tenant scope';
 END IF;

 -- This function checks actual obligation ownership and open amount from
 -- authoritative database, not a customer-provided amount in the HTTP body.
 IF p_kind='CONTRIBUTION' THEN
   IF NOT EXISTS(
     SELECT 1 FROM public.contributions c
     WHERE c.id=p_obligation AND c.tenant_id=p_tenant
       AND c.cycle_id=p_cycle AND c.membership_id=p_membership
       AND c.payment_status<>'QUITADA'
       AND (c.amount_due-c.amount_paid)*100>=p_amount
   ) THEN
     RAISE EXCEPTION 'M038 DENIED: contribution outstanding mismatch';
   END IF;
 ELSE
   IF NOT EXISTS(
     SELECT 1
     FROM public.loan_installments i
     JOIN public.loans l ON l.id=i.loan_id
     WHERE i.id=p_obligation AND i.tenant_id=p_tenant
       AND l.tenant_id=p_tenant AND l.cycle_id=p_cycle
       AND l.borrower_membership_id=p_membership
       AND l.id=p_loan AND l.status IN('DESEMBOLSADO','INADIMPLENTE')
       AND i.status<>'QUITADA'
       AND ((i.principal_due-i.paid_principal)
            +(i.interest_due-i.paid_interest))*100>=p_amount
   ) THEN
     RAISE EXCEPTION 'M038 DENIED: disbursement or installment mismatch';
   END IF;
 END IF;

 PERFORM pg_advisory_xact_lock(pg_catalog.hashtextextended(
   'FRC-M038|'||p_tenant||'|'||p_kind||'|'||p_obligation,0
 ));

 SELECT * INTO current_row
 FROM public.mp_pix_collection_operations_staging
 WHERE operation_id=p_operation FOR UPDATE;
 IF FOUND THEN
   IF current_row.tenant_id<>p_tenant OR current_row.cycle_id<>p_cycle
      OR current_row.membership_id<>p_membership
      OR current_row.obligation_id<>p_obligation
      OR current_row.obligation_kind<>p_kind
      OR current_row.loan_id IS DISTINCT FROM p_loan
      OR current_row.amount_cents<>p_amount
      OR current_row.attempt<>p_attempt
      OR current_row.external_reference<>p_reference
      OR current_row.idempotency_key<>p_key
      OR current_row.expected_collector_id<>p_collector
      OR current_row.terms_version<>p_terms
      OR current_row.environment<>p_environment THEN
     RAISE EXCEPTION 'M038 DENIED: idempotency collision';
   END IF;
   RETURN 'EXISTS';
 END IF;

 SELECT operation_id INTO other_operation
 FROM public.mp_pix_collection_operations_staging
 WHERE tenant_id=p_tenant AND obligation_kind=p_kind
   AND obligation_id=p_obligation
   AND status NOT IN ('FALHOU','REVERTIDO')
 LIMIT 1;
 IF other_operation IS NOT NULL THEN
   RAISE EXCEPTION 'M038 DENIED: active or uncertain Pix attempt';
 END IF;

 INSERT INTO public.mp_pix_collection_operations_staging(
    operation_id,tenant_id,cycle_id,membership_id,obligation_id,
    obligation_kind,loan_id,amount_cents,attempt,external_reference,
    idempotency_key,expected_collector_id,terms_version,environment,status
 ) VALUES(
    p_operation,p_tenant,p_cycle,p_membership,p_obligation,
    p_kind,p_loan,p_amount,p_attempt,p_reference,
    p_key,p_collector,p_terms,p_environment,'PENDENTE'
 );
 RETURN 'NEW';
END $fn$;

CREATE OR REPLACE FUNCTION public.mp_orders_staging_save_checkout(
 p_tenant uuid,p_operation varchar,p_order varchar,p_payment varchar,
 p_qr text,p_qr_image text,p_ticket text
) RETURNS text
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp AS $fn$
DECLARE old_row public.mp_pix_collection_operations_staging%ROWTYPE;
BEGIN
 IF current_database()<>'frcaixinha_staging'
    OR session_user<>'frcaixinha_mp_financial_worker'
    OR p_tenant IS NULL OR p_operation !~ '^P_[0-9a-f]{32}$'
    OR p_order !~ '^ORD[A-Z0-9]{12,77}$'
    OR p_payment !~ '^PAY[A-Z0-9]{12,77}$'
    OR p_qr IS NULL OR length(p_qr) NOT BETWEEN 1 AND 4096
    OR p_qr_image IS NOT NULL AND (
       length(p_qr_image) NOT BETWEEN 1 AND 700000
       OR p_qr_image !~ '^[A-Za-z0-9+/]+={0,2}$'
    )
    OR p_ticket IS NOT NULL AND (
      length(p_ticket)>4096
      OR p_ticket !~ '^https://(www[.])?mercadopago[.]com[.]br/'
    ) THEN
   RAISE EXCEPTION 'M038 DENIED: checkout structure';
 END IF;
 SELECT * INTO old_row
 FROM public.mp_pix_collection_operations_staging
 WHERE tenant_id=p_tenant AND operation_id=p_operation FOR UPDATE;
 IF NOT FOUND OR old_row.environment<>'HOMOLOGACAO'
    OR old_row.status NOT IN ('PENDENTE','AGUARDANDO_PROVEDOR') THEN
   RAISE EXCEPTION 'M038 DENIED: checkout reservation missing';
 END IF;
 IF old_row.provider_order_id IS NOT NULL THEN
   IF old_row.provider_order_id=p_order
      AND old_row.provider_payment_id=p_payment
      AND old_row.qr_code=p_qr
      AND old_row.qr_code_base64 IS NOT DISTINCT FROM p_qr_image
      AND old_row.ticket_url IS NOT DISTINCT FROM p_ticket THEN
      RETURN 'REPLAY';
   END IF;
   RAISE EXCEPTION 'M038 DENIED: conflicting provider checkout';
 END IF;
 UPDATE public.mp_pix_collection_operations_staging
 SET provider_order_id=p_order,provider_payment_id=p_payment,
     qr_code=p_qr,qr_code_base64=p_qr_image,ticket_url=p_ticket,
     status='AGUARDANDO_PROVEDOR',updated_at=now()
 WHERE tenant_id=p_tenant AND operation_id=p_operation;
 RETURN 'INSERTED';
END $fn$;

CREATE OR REPLACE FUNCTION public.mp_orders_staging_mark_uncertain(
 p_tenant uuid,p_operation varchar
) RETURNS text
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp AS $fn$
BEGIN
 IF current_database()<>'frcaixinha_staging'
    OR session_user<>'frcaixinha_mp_financial_worker'
    OR p_tenant IS NULL OR p_operation !~ '^P_[0-9a-f]{32}$' THEN
   RAISE EXCEPTION 'M038 DENIED: uncertain scope';
 END IF;
 UPDATE public.mp_pix_collection_operations_staging
 SET status='PENDENTE_CONCILIACAO',updated_at=now()
 WHERE tenant_id=p_tenant AND operation_id=p_operation
   AND status='PENDENTE' AND provider_order_id IS NULL;
 IF FOUND THEN RETURN 'UNCERTAIN'; END IF;
 RETURN 'UNCHANGED';
END $fn$;

CREATE OR REPLACE FUNCTION public.mp_orders_staging_get_checkout(
 p_tenant uuid,p_operation varchar
) RETURNS TABLE(
   operation_id varchar(64),order_id varchar(80),
   payment_id varchar(80),amount_cents bigint,
   status varchar(32),qr_code text,qr_image text,ticket_url text
)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp AS $fn$
BEGIN
 IF current_database()<>'frcaixinha_staging'
    OR session_user<>'frcaixinha_mp_financial_worker'
    OR p_tenant IS NULL OR p_operation !~ '^P_[0-9a-f]{32}$' THEN
   RAISE EXCEPTION 'M038 DENIED: checkout read scope';
 END IF;
 RETURN QUERY SELECT c.operation_id,c.provider_order_id,
   c.provider_payment_id,c.amount_cents,c.status,
   c.qr_code,c.qr_code_base64,c.ticket_url
 FROM public.mp_pix_collection_operations_staging c
 WHERE c.tenant_id=p_tenant AND c.operation_id=p_operation
   AND c.provider_order_id IS NOT NULL
   AND c.status='AGUARDANDO_PROVEDOR';
END $fn$;

REVOKE ALL ON FUNCTION public.mp_orders_staging_reserve(
 uuid,uuid,uuid,uuid,varchar,uuid,bigint,smallint,
 varchar,varchar,varchar,varchar,varchar,varchar
) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.mp_orders_staging_save_checkout(
 uuid,varchar,varchar,varchar,text,text,text
) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.mp_orders_staging_mark_uncertain(
 uuid,varchar
) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.mp_orders_staging_get_checkout(
 uuid,varchar
) FROM PUBLIC;

GRANT EXECUTE ON FUNCTION public.mp_orders_staging_reserve(
 uuid,uuid,uuid,uuid,varchar,uuid,bigint,smallint,
 varchar,varchar,varchar,varchar,varchar,varchar
) TO frcaixinha_mp_financial_worker;
GRANT EXECUTE ON FUNCTION public.mp_orders_staging_save_checkout(
 uuid,varchar,varchar,varchar,text,text,text
) TO frcaixinha_mp_financial_worker;
GRANT EXECUTE ON FUNCTION public.mp_orders_staging_mark_uncertain(
 uuid,varchar
) TO frcaixinha_mp_financial_worker;
GRANT EXECUTE ON FUNCTION public.mp_orders_staging_get_checkout(
 uuid,varchar
) TO frcaixinha_mp_financial_worker;

-- No EXECUTE privilege for general application. NO settlement/ledger write.
COMMIT;
