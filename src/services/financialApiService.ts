/**
 * FRcaixinha 2.2 — Serviço Central de API Financeira
 * Integra o frontend diretamente aos endpoints oficiais FastAPI + PostgreSQL.
 *
 * REGRA INVIOLÁVEL:
 * Se o backend FastAPI/PostgreSQL não estiver disponível (HTTP 503 / Network Error),
 * a operação financeira DEVE falhar de forma explícita e auditável.
 * É expressamente PROIBIDO gravar silenciosamente operações financeiras em localStorage!
 */

import { authService, getApiBaseUrl } from './authService';

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

class FinancialApiService {
  private async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const baseUrl = getApiBaseUrl();
    const url = `${baseUrl}${path}`;
    const token = authService.getToken();

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
      throw new FinancialBackendUnavailableError(
        'Falha de Conexão com o Backend FastAPI. O servidor não pôde ser contatado.',
        'NETWORK_CONNECTION_FAILED',
        netErr?.message
      );
    }

    if (!response.ok) {
      let errBody: any = null;
      try {
        errBody = await response.json();
      } catch {
        // Ignora falha de parse
      }

      if (response.status === 401) {
        authService.invalidateSession();
        throw new Error('Sessão expirada ou revogada. Faça login novamente.');
      }

      if (response.status === 503) {
        throw new FinancialBackendUnavailableError(
          errBody?.message || 'Backend oficial FastAPI / PostgreSQL não conectado. Operação financeira bloqueada com segurança.',
          errBody?.code || 'FASTAPI_BACKEND_UNAVAILABLE',
          errBody?.detail || 'O Contrato Técnico Mestre exige persistência transacional com RLS. Gravações locais são vedadas.'
        );
      }

      if (response.status === 403) {
        throw new Error(errBody?.detail?.message || errBody?.detail || errBody?.message || 'Acesso negado pelas regras de governança ou segregação patrimonial.');
      }

      throw new Error(errBody?.detail || errBody?.message || `Erro na API (${response.status}): ${response.statusText}`);
    }

    return response.json();
  }

  // --- Cotas e Contribuições ---

  public async fetchQuotas(tenantId: string) {
    return this.request<any[]>(`/api/v1/tenants/${tenantId}/quotas`);
  }

  public async fetchContributions(tenantId: string) {
    return this.request<any[]>(`/api/v1/tenants/${tenantId}/contributions`);
  }

  public async payContribution(tenantId: string, contributionId: string, amount: number) {
    return this.request<any>(`/api/v1/tenants/${tenantId}/contributions/${contributionId}/pay`, {
      method: 'POST',
      body: JSON.stringify({ amount }),
    });
  }

  // --- Empréstimos e Tabela Price ---

  public async simulateLoan(tenantId: string, payload: { principal: number; term_months: number; monthly_rate?: number }) {
    return this.request<any>(`/api/v1/tenants/${tenantId}/loans/simulate`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  public async fetchLoans(tenantId: string) {
    return this.request<any[]>(`/api/v1/tenants/${tenantId}/loans`);
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

  // --- Livro-Razão Contábil ---

  public async fetchLedgerAccounts(tenantId: string) {
    return this.request<any[]>(`/api/v1/tenants/${tenantId}/ledger/accounts`);
  }

  public async fetchLedgerTransactions(tenantId: string) {
    return this.request<any[]>(`/api/v1/tenants/${tenantId}/ledger/transactions`);
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
