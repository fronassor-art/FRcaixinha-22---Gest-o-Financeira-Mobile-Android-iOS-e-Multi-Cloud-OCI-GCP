/**
 * FRcaixinha AI Studio Mobile — Serviço Central de API Financeira
 * Integra o frontend diretamente aos endpoints oficiais FastAPI + PostgreSQL.
 *
 * REGRA INVIOLÁVEL:
 * Se o backend FastAPI/PostgreSQL não estiver disponível (HTTP 503 / Network Error),
 * a operação financeira DEVE falhar de forma explícita e auditável.
 * É expressamente PROIBIDO gravar silenciosamente operações financeiras em localStorage!
 */

import { authService, getApiBaseUrl, AuthSessionSnapshot } from './authService';
import { parseMasterTenantRegistry, registryQuery, MasterRegistryPage, RegistryStatus } from './masterRegistry';
import { parseMasterAdminRegistry, adminRegistryQuery, MasterAdminRegistryPage } from './masterAdminRegistry';
import {parseMasterSaasPortfolio, MasterSaasPortfolio, SaasStatusFilter} from './masterSaasPortfolio';
import {
  MasterOnboardingCapabilities, MasterOnboardingPreflight,
  parseOnboardingCapabilities, parseOnboardingPreflight,
} from './masterOnboarding';
import {
  WorkflowContract, WorkflowPreview, WorkflowPreviewRequest,
  parseWorkflowContract, parseWorkflowPreview, validateWorkflowPreviewRequest,
} from './masterWorkflow';
import {MasterPermissionMatrix, parseMasterPermissionMatrix} from './masterPermissionMatrix';
import {
  TenantDashboard, TenantMembersPage, assertTenantReadScope,
  parseTenantDashboard, parseTenantMembers,
} from './tenantReadBoundary';
import {DisplayLoan, parseTenantLoans} from './loanReadBoundary';
import {LoanSimulation, parseLoanSimulation, validateSimulationRequest} from './loanSimulationBoundary';
import {DisplayContribution, normalizeContributions} from './contributionsData';
import {MemberAnnualPreview, parseMemberAnnualPreview} from './memberAnnualPreview';
import {MemberCycleRiskPreview,parseMemberCycleRiskPreview} from './memberCycleRiskBoundary';
import {LedgerIntegrityPreview, parseLedgerIntegrityPreview} from './ledgerIntegrityPreview';
import {LedgerAccountJournalPage, parseLedgerAccountJournalPage} from './ledgerAccountJournalBoundary';
import {LedgerAccountDirectory,parseLedgerAccountDirectory} from './ledgerAccountDirectoryBoundary';
import {LedgerKeysetPage,parseLedgerKeysetPage} from './ledgerKeysetBoundary';
import {DisplayLedgerAccount,DisplayLedgerTransaction,parseLedgerAccounts,parseLedgerTransactions} from './ledgerDetailBoundary';
import {ApiResponseIntegrityError, parseApiErrorEnvelope} from './apiResponsePolicy';

export class FinancialBackendUnavailableError extends Error {
  public code: string;
  public detail?: string;

  constructor(message: string, code: string = 'FASTAPI_BACKEND_UNAVAILABLE', detail?: string) {
    super(message);
    this.name = 'FinancialBackendUnavailableError';
    this.code = code;
    this.detail = detail;
  }
}

/** Status explícito do HTTP, sem transformar erros em permissões.
 * Mensagens provêm do parser que elimina conteúdo suspeito.
 */
export class FinancialApiHttpError extends Error {
  constructor(message: string, public readonly status: number) {
    super(message);
    this.name = 'FinancialApiHttpError';
  }
}

export class SessionBoundaryError extends Error {
  constructor(
    message: string,
    public readonly code: 'SESSION_REQUIRED' | 'SESSION_CHANGED_DURING_REQUEST'
  ) {
    super(message);
    this.name = 'SessionBoundaryError';
  }
}

function assertSessionNotChanged(snapshot: AuthSessionSnapshot): void {
  if (!authService.isSessionSnapshotCurrent(snapshot)) {
    throw new SessionBoundaryError(
      'O acesso mudou durante a consulta. Descarte o resultado anterior.',
      'SESSION_CHANGED_DURING_REQUEST'
    );
  }
}

class FinancialApiService {
  private async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const baseUrl = getApiBaseUrl();
    const url = `${baseUrl}${path}`;
    const snapshot = authService.captureSession();
    if (!snapshot.token) {
      throw new SessionBoundaryError(
        'Sessão ausente ou expirada. Entre novamente para consultar dados.',
        'SESSION_REQUIRED'
      );
    }
    const token = snapshot.token;

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'X-FRcaixinha-Client': 'web-react-19',
      ...(options.headers as Record<string, string> || {}),
    };

    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    let response: Response;
    try {
      response = await fetch(url, {
        ...options,
        headers,
      });
    } catch (netErr: any) {
      assertSessionNotChanged(snapshot);
      throw new FinancialBackendUnavailableError(
        'Falha de Conexão com o Backend FastAPI. O servidor não pôde ser contatado.',
        'NETWORK_CONNECTION_FAILED',
        netErr?.message
      );
    }

    assertSessionNotChanged(snapshot);

    if (!response.ok) {
      // HTTP status define a política; texto externo nunca controla autorização.
      // 401 é tratado ANTES do corpo para evitar depender de JSON malformado.
      if (response.status === 401) {
        authService.invalidateSessionIfCurrent(snapshot);
        throw new SessionBoundaryError(
          'Sessão expirada ou revogada. Faça login novamente.',
          'SESSION_REQUIRED'
        );
      }
      let errorBody: unknown = null;
      try {
        errorBody = await response.json();
      } catch {
        // API/proxy pode responder HTML, texto ou body vazio.
      }
      assertSessionNotChanged(snapshot);
      const error = parseApiErrorEnvelope(errorBody);

      if (response.status === 503) {
        throw new FinancialBackendUnavailableError(
          error.message ||
            'Backend oficial FastAPI / PostgreSQL indisponível. Operação bloqueada com segurança.',
          error.code || 'FASTAPI_BACKEND_UNAVAILABLE',
          error.detail || 'Persistência transacional confirmada pelo PostgreSQL é obrigatória.'
        );
      }

      if (response.status === 403) {
        throw new FinancialApiHttpError(error.detail || error.message ||
          'Acesso negado pelas regras de governança ou segregação patrimonial.', 403);
      }

      throw new FinancialApiHttpError(error.detail || error.message ||
        `Erro na API (${response.status}). Operação não confirmada.`, response.status);
    }

    let data: T;
    try {
      data = await response.json();
    } catch {
      assertSessionNotChanged(snapshot);
      throw new ApiResponseIntegrityError(
        'O servidor retornou uma resposta inválida. Nenhum dado foi confirmado.'
      );
    }
    assertSessionNotChanged(snapshot);
    return data;
  }

  // --- Consultas de painéis (somente dados autoritativos, sem seed) ---

  public async fetchMasterOverview(): Promise<{
    source: 'POSTGRESQL_RLS';
    total_tenants: number;
    tenants: Array<{ id: string; display_name: string; status: string; is_owner_box: boolean }>;
    has_more: boolean;
    saas_revenue_status: string;
    subscriptions_status: string;
  }> {
    return this.request('/api/v1/master/overview');
  }

  public async fetchMasterTenantRegistry(params: {
    search: string; status: RegistryStatus; page: number; pageSize?: number;
  }): Promise<MasterRegistryPage> {
    const raw: unknown = await this.request('/api/v1/master/tenant-registry?' + registryQuery(params));
    return parseMasterTenantRegistry(raw);
  }

  public async fetchMasterAdminRegistry(params: {
    search: string; page: number; pageSize?: number;
  }): Promise<MasterAdminRegistryPage> {
    const raw: unknown = await this.request('/api/v1/master/admin-registry?' + adminRegistryQuery(params));
    return parseMasterAdminRegistry(raw);
  }

  public async fetchMasterOnboardingCapabilities(): Promise<MasterOnboardingCapabilities> {
    const raw: unknown = await this.request('/api/v1/master/admin-onboarding/capabilities');
    return parseOnboardingCapabilities(raw);
  }

  public async simulateMasterOnboarding(params: {
    tenantId: string; candidateUserId?: string; purpose: string;
  }): Promise<MasterOnboardingPreflight> {
    const raw: unknown = await this.request('/api/v1/master/admin-onboarding/preflight', {
      method: 'POST',
      body: JSON.stringify({
        tenant_id: params.tenantId,
        target_role: 'TENANT_ADMIN',
        ...(params.candidateUserId ? { candidate_user_id: params.candidateUserId } : {}),
        purpose: params.purpose,
      }),
    });
    return parseOnboardingPreflight(raw);
  }

  public async fetchMasterPermissionMatrix(): Promise<MasterPermissionMatrix> {
    const raw: unknown = await this.request('/api/v1/master/admin-onboarding/permission-matrix');
    return parseMasterPermissionMatrix(raw);
  }

  public async fetchMasterWorkflowContract(): Promise<WorkflowContract> {
    const raw: unknown = await this.request('/api/v1/master/admin-onboarding/workflow-contract');
    return parseWorkflowContract(raw);
  }

  public async previewMasterWorkflowTransition(params: WorkflowPreviewRequest): Promise<WorkflowPreview> {
    validateWorkflowPreviewRequest(params);
    const raw: unknown = await this.request('/api/v1/master/admin-onboarding/transition-preview', {
      method: 'POST',
      body: JSON.stringify({
        current_state: params.currentState,
        proposed_state: params.proposedState,
        simulated_actor_role: params.actorRole,
        candidate_is_actor: params.candidateIsActor,
        email_verified: params.emailVerified,
        tenant_active: params.tenantActive,
        independent_approval: params.independentApproval,
        token_valid: params.tokenValid,
        expected_revision: params.expectedRevision,
        observed_revision: params.observedRevision,
        idempotency_key: params.idempotencyKey,
        previously_used_keys: params.previouslyUsedKeys,
      }),
    });
    return parseWorkflowPreview(raw);
  }

  private currentTenantReader() {
    const user = authService.getUser();
    if (!user) throw new SessionBoundaryError(
      'Sessão ausente ou expirada. Faça login novamente.',
      'SESSION_REQUIRED'
    );
    return user;
  }

  public async fetchTenantOverview(tenantId: string): Promise<TenantDashboard> {
    const role = assertTenantReadScope(this.currentTenantReader(), tenantId, 'DASHBOARD');
    const raw: unknown = await this.request(`/api/v1/tenants/${encodeURIComponent(tenantId)}/dashboard`);
    return parseTenantDashboard(raw, tenantId, role);
  }

  public async fetchTenantMembers(tenantId: string): Promise<TenantMembersPage> {
    assertTenantReadScope(this.currentTenantReader(), tenantId, 'MEMBERS');
    const raw: unknown = await this.request(`/api/v1/tenants/${encodeURIComponent(tenantId)}/members`);
    return parseTenantMembers(raw, tenantId);
  }


  /** Consulta read-only Master, valida contexto e esquema recebido. */
  public async fetchMasterSaasPortfolio(search: string,page: number,filter:SaasStatusFilter='TODOS'):Promise<MasterSaasPortfolio> {
    if(!Number.isSafeInteger(page)||page<1||page>1000)throw Error('Página inválida');
    if(!['TODOS','RASCUNHO_INATIVO','ATIVO','SUSPENSO','ENCERRADO'].includes(filter))
      throw Error('Filtro inválido');
    const cleaned=search.trim();
    if(cleaned.length>80)throw Error('Busca muito longa');
    const params=new URLSearchParams({search:cleaned,page:String(page),tenant_status:filter});
    const raw:unknown=await this.request('/api/v1/master/saas-portfolio?'+params.toString());
    return parseMasterSaasPortfolio(raw,filter,page);
  }

  // --- Catalogo e precos persistentes do Master (sem cobranca) ---

  public async fetchMasterLicenses(): Promise<{
    source: 'POSTGRESQL_RLS';
    billing_status: string;
    plans: Array<{
      tier: 'ESSENCIAL' | 'INTERMEDIARIO' | 'AMPLIADO';
      name: string;
      members_limit: number | null;
      quotas_limit: number | null;
      status: string;
      version_id: string | null;
      monthly_price: string | null;
      annual_price_computed: string | null;
      updated_at: string | null;
    }>;
  }> {
    return this.request('/api/v1/master/licenses');
  }

  public async fetchMasterSubscriptionPreparations(): Promise<{
    source: 'POSTGRESQL_RLS';
    billing_status: string;
    total_returned: number;
    preparations: Array<{
      id: string; tenant_id: string; plan_tier: string; price_version_id: string;
      billing_period: string; status: string; created_at: string;
    }>;
  }> {
    return this.request('/api/v1/master/subscription-preparations');
  }

  public async fetchTenantLicensePreparation(tenantId: string): Promise<{
    source: 'POSTGRESQL_RLS';
    tenant_id: string;
    billing_status: string;
    preparations: Array<{
      id: string; plan_tier: string; price_version_id: string;
      billing_period: string; status: string; created_at: string;
    }>;
  }> {
    return this.request(`/api/v1/tenants/${encodeURIComponent(tenantId)}/license-preparation`);
  }

  public async fetchMyContractAcceptances(tenantId: string): Promise<{
    source: 'POSTGRESQL_RLS';
    tenant_id: string;
    contracts: Array<{
      id: string; document_id: string; kind: string; version: string;
      sha256: string; source_reference: string; accepted_at: string;
    }>;
  }> {
    return this.request(`/api/v1/tenants/${encodeURIComponent(tenantId)}/my-contracts`);
  }

  // Status documental/financeiro SaaS (nunca exibe ledger de tenants)
  public async fetchMasterSaasPaymentStatus(): Promise<{
    source: 'POSTGRESQL_RLS';
    payments: Array<{id:string;tenant_id:string;status:string;
      expected_amount_cents:number;currency:string;created_at:string}>;
    licenses: Array<{id:string;tenant_id:string;plan_tier:string;
      status:string;effective_status:string;valid_from:string;valid_until:string}>;
  }> {
    return this.request('/api/v1/master/saas-payment-status');
  }

  public async fetchTenantSaasPaymentStatus(tenantId: string): Promise<{
    source: 'POSTGRESQL_RLS'; tenant_id:string;
    payments: Array<{id:string;status:string;expected_amount_cents:number;
      currency:string;created_at:string}>;
    licenses: Array<{id:string;plan_tier:string;status:string;
      effective_status:string;valid_from:string;valid_until:string}>;
  }> {
    return this.request(`/api/v1/tenants/${encodeURIComponent(tenantId)}/saas-payment-status`);
  }

  public async fetchMasterIntegrationReadiness(): Promise<{
    invitation_delivery: string;
    saas_platform_payment: string;
    environment: string;
  }> {
    return this.request('/api/v1/master/integration-readiness');
  }

  public async updateMasterLicensePrice(
    tier: 'ESSENCIAL' | 'INTERMEDIARIO',
    monthly_price: number,
    reason: string
  ): Promise<{ status: string; version_id: string; monthly_price: string;
    annual_price_computed: string }> {
    return this.request('/api/v1/master/license-prices', {
      method: 'POST', body: JSON.stringify({ tier, monthly_price, reason }),
    });
  }

  // --- Cotas e Contribuições ---

  public async fetchQuotas(tenantId: string) {
    return this.request<any[]>(`/api/v1/tenants/${tenantId}/quotas`);
  }

  public async fetchContributions(tenantId: string): Promise<DisplayContribution[]> {
    assertTenantReadScope(this.currentTenantReader(), tenantId, 'DASHBOARD');
    const raw: unknown=await this.request(
      `/api/v1/tenants/${encodeURIComponent(tenantId)}/contributions`);
    return normalizeContributions(raw,tenantId);
  }

  public async payContribution(tenantId: string, contributionId: string, amount: number) {
    return this.request<any>(`/api/v1/tenants/${tenantId}/contributions/${contributionId}/pay`, {
      method: 'POST',
      body: JSON.stringify({ amount }),
    });
  }

  // --- Empréstimos e Tabela Price ---

  public async simulateLoan(tenantId: string, payload: { principal: number; term_months: number }): Promise<LoanSimulation> {
    assertTenantReadScope(this.currentTenantReader(), tenantId, 'DASHBOARD');
    const checked=validateSimulationRequest(payload);
    const raw:unknown=await this.request(`/api/v1/tenants/${encodeURIComponent(tenantId)}/loans/simulate`, {
      method: 'POST',
      body: JSON.stringify(checked),
    });
    return parseLoanSimulation(raw,checked);
  }

  public async fetchLoans(tenantId: string): Promise<DisplayLoan[]> {
    assertTenantReadScope(this.currentTenantReader(), tenantId, 'DASHBOARD');
    const raw: unknown = await this.request(`/api/v1/tenants/${encodeURIComponent(tenantId)}/loans`);
    return parseTenantLoans(raw, tenantId);
  }

  public async requestLoan(tenantId: string, payload: { principal: number; term_months: number; is_admin_loan?: boolean; justification?: string }) {
    return this.request<any>(`/api/v1/tenants/${tenantId}/loans/request`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  public async approveLoan(tenantId: string, loanId: string) {
    return this.request<any>(`/api/v1/tenants/${tenantId}/loans/${loanId}/approve`, {
      method: 'POST',
    });
  }

  public async disburseLoan(tenantId: string, loanId: string) {
    return this.request<any>(`/api/v1/tenants/${tenantId}/loans/${loanId}/disburse`, {
      method: 'POST',
    });
  }

  public async repayLoan(tenantId: string, loanId: string, amount: number) {
    return this.request<any>(`/api/v1/tenants/${tenantId}/loans/${loanId}/repay`, {
      method: 'POST',
      body: JSON.stringify({ amount }),
    });
  }

  public async settleLoanEarly(tenantId: string, loanId: string) {
    return this.request<any>(`/api/v1/tenants/${tenantId}/loans/${loanId}/early-settlement`, {
      method: 'POST',
    });
  }

  /** Prévia registrada no PostgreSQL para o Membro, sem cálculo de lucro. */
  /** M531: consulta de risco registrada — não confirma Pix, nem bloqueia membro. */
  public async fetchMemberCycleRiskPreview(
    tenantId:string,year:number,asOf:string,memberId?:string
  ):Promise<MemberCycleRiskPreview>{
    const reader=assertTenantReadScope(this.currentTenantReader(),tenantId,'DASHBOARD');
    if(!Number.isSafeInteger(year)||year<2020||year>2100||
      !/^\d{4}-\d{2}-\d{2}$/.test(asOf))
      throw Error('Ano/data inválidos para a prévia do ciclo');
    if(reader==='TENANT_MEMBER'&&memberId!==undefined)
      throw Error('Membro não pode selecionar outro vínculo');
    if(reader==='TENANT_ADMIN'&&(!memberId||
      !/^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i.test(memberId)))
      throw Error('Administrador precisa selecionar um vínculo válido');
    const tail=reader==='TENANT_ADMIN'
      ?'/members/'+encodeURIComponent(memberId as string):'/me';
    const endpoint='/api/v1/tenants/'+encodeURIComponent(tenantId)+
      '/cycles/'+year+'/member-risk'+tail+'?as_of='+encodeURIComponent(asOf);
    const raw:unknown=await this.request(endpoint);
    return parseMemberCycleRiskPreview(raw,tenantId,year,reader,memberId);
  }

  public async fetchMemberAnnualPreview(tenantId:string,year=2027):Promise<MemberAnnualPreview>{
    const role=assertTenantReadScope(this.currentTenantReader(),tenantId,'DASHBOARD');
    if(role!=='TENANT_MEMBER')throw new Error('Demonstrativo somente para Membro');
    if(!Number.isInteger(year)||year<2020||year>2100)throw Error('Ano inválido');
    const raw:unknown=await this.request(
      `/api/v1/tenants/${encodeURIComponent(tenantId)}/contributions/annual-preview/me?year=${year}`
    );
    return parseMemberAnnualPreview(raw,tenantId,year);
  }

  /** Prévia administrativa: somente consolidação de obrigações registradas. */
  public async fetchAdminAnnualPreview(tenantId:string,year=2027):Promise<MemberAnnualPreview>{
    const role=assertTenantReadScope(this.currentTenantReader(),tenantId,'DASHBOARD');
    if(role!=='TENANT_ADMIN')throw Error('Prévia exclusiva do Administrador');
    if(!Number.isInteger(year)||year<2020||year>2100)throw Error('Ano inválido');
    const raw:unknown=await this.request(
      `/api/v1/tenants/${encodeURIComponent(tenantId)}/contributions/annual-preview/admin?year=${year}`
    );
    return parseMemberAnnualPreview(raw,tenantId,year);
  }

  // --- Livro-Razão Contábil — nunca para Master ou Membro ---

  private assertLedgerAdmin(tenantId:string):void {
    const role=assertTenantReadScope(this.currentTenantReader(),tenantId,'DASHBOARD');
    if(role!=='TENANT_ADMIN')throw Error('Livro-Razão somente para administrador da caixinha.');
  }

  public async fetchLedgerIntegrityPreview(tenantId:string):Promise<LedgerIntegrityPreview> {
    this.assertLedgerAdmin(tenantId);
    const raw:unknown=await this.request(
      `/api/v1/tenants/${encodeURIComponent(tenantId)}/ledger/integrity-preview`
    );
    return parseLedgerIntegrityPreview(raw,tenantId);
  }

  /** Diretório de contas sem saldos, inclusive com zero transações. */
  public async fetchLedgerAccountDirectory(tenantId:string):Promise<LedgerAccountDirectory> {
    this.assertLedgerAdmin(tenantId);
    const raw:unknown=await this.request(
      '/api/v1/tenants/'+encodeURIComponent(tenantId)+'/ledger/accounts/directory'
    );
    return parseLedgerAccountDirectory(raw,tenantId);
  }

  public async fetchLedgerAccounts(tenantId: string):Promise<DisplayLedgerAccount[]> {
    this.assertLedgerAdmin(tenantId);
    const raw:unknown=await this.request(`/api/v1/tenants/${encodeURIComponent(tenantId)}/ledger/accounts`);
    return parseLedgerAccounts(raw,tenantId);
  }

  public async fetchLedgerTransactions(tenantId: string):Promise<DisplayLedgerTransaction[]> {
    this.assertLedgerAdmin(tenantId);
    const raw:unknown=await this.request(`/api/v1/tenants/${encodeURIComponent(tenantId)}/ledger/transactions`);
    return parseLedgerTransactions(raw,tenantId);
  }

  /** Página por cursor: leitura parcial, nova autorizacao no backend a cada GET. */
  public async fetchLedgerAccountKeyset(
    tenantId:string,accountId:string,cursor:string|null,pageSize=25
  ):Promise<LedgerKeysetPage> {
    this.assertLedgerAdmin(tenantId);
    if(!Number.isSafeInteger(pageSize)||pageSize<1||pageSize>50||
       (cursor!==null&&!/^[A-Za-z0-9_-]{1,400}$/.test(cursor)))
      throw Error('Parâmetros do cursor contábil inválidos.');
    const params=new URLSearchParams({page_size:String(pageSize)});
    if(cursor!==null)params.set('cursor',cursor);
    const raw:unknown=await this.request(
      '/api/v1/tenants/'+encodeURIComponent(tenantId)+
      '/ledger/accounts/'+encodeURIComponent(accountId)+
      '/entries/keyset?'+params.toString()
    );
    return parseLedgerKeysetPage(raw,tenantId,accountId,pageSize);
  }

  /** Pagina de uma conta: read-only, nunca significa conciliacao. */
  public async fetchLedgerAccountJournal(
    tenantId:string,accountId:string,page:number,pageSize:number=25
  ):Promise<LedgerAccountJournalPage>{
    this.assertLedgerAdmin(tenantId);
    if(!Number.isSafeInteger(page)||page<1||page>1000||
       !Number.isSafeInteger(pageSize)||pageSize<1||pageSize>50)
      throw Error('Parâmetros de paginação inválidos.');
    const raw:unknown=await this.request(
      '/api/v1/tenants/'+encodeURIComponent(tenantId)+
      '/ledger/accounts/'+encodeURIComponent(accountId)+
      '/entries?page='+page+'&page_size='+pageSize
    );
    return parseLedgerAccountJournalPage(raw,tenantId,accountId,page,pageSize);
  }

  // --- Consentimento de Autoempréstimo de Admin ---

  public async fetchAdminConsentStatus(tenantId: string, loanId?: string) {
    const q = loanId ? `?loan_id=${loanId}` : '';
    return this.request<any>(`/api/v1/tenants/${tenantId}/admin-self-consent${q}`);
  }

  public async voteAdminConsent(tenantId: string, loanId: string, decision: 'FAVORAVEL' | 'CONTRARIO', justification?: string) {
    return this.request<any>(`/api/v1/tenants/${tenantId}/admin-self-consent/vote?loan_id=${loanId}`, {
      method: 'POST',
      body: JSON.stringify({ decision, justification }),
    });
  }

  // --- Fechamento Anual de Ciclo ---

  public async closeCycle(tenantId: string, cycleId: string) {
    return this.request<any>(`/api/v1/tenants/${tenantId}/closings`, {
      method: 'POST',
      body: JSON.stringify({ cycle_id: cycleId }),
    });
  }

  public async fetchCycleClosing(tenantId: string, cycleId: string) {
    return this.request<any>(`/api/v1/tenants/${tenantId}/closings/${cycleId}`);
  }

  // --- Auditoria ---

  public async fetchAuditEvents(tenantId: string) {
    return this.request<any[]>(`/api/v1/tenants/${tenantId}/audit-events`);
  }
}

export const financialApi = new FinancialApiService();
