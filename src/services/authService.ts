/**
 * FRcaixinha 2.2 - Serviço de Autenticação com Fronteira de Servidor Real
 * Implementa comunicação com /api/auth, guarda tokens sensíveis exclusivamente em memória
 * e encerra sessões expiradas conforme exigência de segurança e LGPD.
 */

export interface AuthenticatedUser {
  id: string;
  name: string;
  email: string;
  role: 'MASTER' | 'TENANT_ADMIN' | 'TENANT_MEMBER';
  tenantId?: string;
}

export interface AuthContext {
  role: AuthenticatedUser['role'];
  tenant_id: string | null;
}

export interface AuthStatusResponse {
  status: string;
  configured: boolean;
  provider: string;
  sessionTimeoutSeconds: number;
  requiresAuthentication: boolean;
  message: string;
  serverTime: string;
}

function serverUser(user: any): AuthenticatedUser {
  if (!user || !['MASTER', 'TENANT_ADMIN', 'TENANT_MEMBER'].includes(user.role)) throw new Error('Resposta de identidade inválida.');
  return { id: user.id, name: user.name, email: user.email, role: user.role, tenantId: user.tenant_id ?? user.tenantId };
}

/**
 * Obtém a URL base do backend de forma explícita e segura.
 * Nunca embute IPs privados fictícios ou credenciais no cliente.
 * Se VITE_API_URL não for informada em builds nativos móveis, avisa explicitamente.
 */
export function getApiBaseUrl(): string {
  const envUrl = (import.meta as any).env?.VITE_API_URL;
  if (envUrl && typeof envUrl === 'string' && envUrl.trim().length > 0) {
    return envUrl.replace(/\/$/, '');
  }
  return '';
}

export function isNativeMobilePlatform(): boolean {
  return Boolean(typeof window !== 'undefined' && (window as any).Capacitor?.isNativePlatform?.());
}

class AuthService {
  // ATENÇÃO: Tokens e credenciais ficam em memória e NUNCA em localStorage
  private token: string | null = null;
  private user: AuthenticatedUser | null = null;
  private expiresAt: number | null = null;
  private listeners: (() => void)[] = [];
  private expirationTimer: number | null = null;

  constructor() {
    // Inicialização segura: sem sessão ativa por padrão
    this.token = null;
    this.user = null;
    this.expiresAt = null;
  }

  public subscribe(listener: () => void): () => void {
    this.listeners.push(listener);
    return () => {
      this.listeners = this.listeners.filter(l => l !== listener);
    };
  }

  private notify() {
    this.listeners.forEach(l => l());
  }

  public isAuthenticated(): boolean {
    if (!this.token || !this.user || !this.expiresAt) return false;
    if (Date.now() >= this.expiresAt) {
      this.handleSessionExpired();
      return false;
    }
    return true;
  }

  public getToken(): string | null {
    return this.isAuthenticated() ? this.token : null;
  }

  public getUser(): AuthenticatedUser | null {
    if (!this.isAuthenticated()) return null;
    return this.user;
  }

  public getExpiresAt(): number | null {
    return this.expiresAt;
  }

  public async checkAuthStatus(): Promise<AuthStatusResponse> {
    if (isNativeMobilePlatform() && !getApiBaseUrl()) {
      return {
        status: 'BLOCKED_PENDING_CONFIG',
        configured: false,
        provider: 'NONE',
        sessionTimeoutSeconds: 900,
        requiresAuthentication: true,
        message: 'Backend móvel não configurado. Defina a variável VITE_API_URL apontando para o servidor FastAPI antes do build.',
        serverTime: new Date().toISOString(),
      };
    }

    try {
      const res = await fetch(`${getApiBaseUrl()}/api/v1/auth/status`, {
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
        credentials: 'include',
      });
      if (!res.ok) throw new Error('Falha ao verificar status de autenticação do servidor');
      return await res.json();
    } catch {
      return {
        status: 'BLOCKED_PENDING_CONFIG',
        configured: false,
        provider: 'NONE',
        sessionTimeoutSeconds: 900,
        requiresAuthentication: true,
        message: 'Autenticação ainda não configurada. Nenhuma sessão foi iniciada.',
        serverTime: new Date().toISOString(),
      };
    }
  }

  /**
   * Consulta o servidor em /api/auth/me para validar a sessão ativa.
   * O frontend só considera autenticado após confirmação com HTTP 200 do servidor.
   */
  public async checkCurrentUser(): Promise<AuthenticatedUser | null> {
    if (isNativeMobilePlatform() && !getApiBaseUrl()) {
      return null;
    }
    if (!this.token) return null;

    try {
      const headers: Record<string, string> = {
        'X-Requested-With': 'XMLHttpRequest',
      };
      if (this.token) {
        headers['Authorization'] = `Bearer ${this.token}`;
      }

      const res = await fetch(`${getApiBaseUrl()}/api/v1/auth/me`, {
        method: 'GET',
        headers,
        credentials: 'include',
      });

      if (!res.ok) {
        this.clearSession();
        this.notify();
        return null;
      }

      const data = await res.json();
      if (data && (data.user || data.id)) {
        const expiration: number = data.expiresAt || (Date.now() + 15 * 60 * 1000);
        this.user = serverUser(data.user || data);
        this.expiresAt = expiration;
        this.armExpirationTimer(expiration);
        this.notify();
        return this.user;
      }
      return null;
    } catch {
      this.clearSession();
      this.notify();
      return null;
    }
  }

  public async login(usernameOrEmail: string, password: string): Promise<AuthenticatedUser> {
    if (isNativeMobilePlatform() && !getApiBaseUrl()) {
      throw new Error('Servidor backend móvel não configurado. Defina VITE_API_URL apontando para a API FastAPI antes de gerar o APK.');
    }

    const res = await fetch(`${getApiBaseUrl()}/api/v1/auth/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
      },
      credentials: 'include',
      body: JSON.stringify({ usernameOrEmail, password }),
    });

    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.detail || data.message || data.error || 'Falha ao autenticar.');
    }

    // Armazenamento EXCLUSIVO em memória (RAM transitória)
    const expiresAt = data.expiresAt ?? Date.parse(data.expires_at);
    if (!data.token || !Number.isFinite(expiresAt) || expiresAt <= Date.now()) throw new Error('Sessão inválida recebida do servidor.');
    this.token = data.token;
    this.user = serverUser(data.user);
    this.expiresAt = expiresAt;

    this.armExpirationTimer(expiresAt);
    this.notify();

    return this.user!;
  }

  public async listContexts(): Promise<AuthContext[]> {
    if (!this.isAuthenticated()) return [];
    const res = await fetch(getApiBaseUrl() + '/api/v1/auth/contexts', {
      headers: { Authorization: 'Bearer ' + this.token },
    });
    if (res.status === 401) { this.invalidateSession(); return []; }
    if (!res.ok) throw new Error('Não foi possível consultar os vínculos.');
    return res.json();
  }

  public async switchContext(context: AuthContext): Promise<AuthenticatedUser> {
    if (!this.isAuthenticated()) throw new Error('Sessão expirada.');
    const res = await fetch(getApiBaseUrl() + '/api/v1/auth/switch-context', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + this.token },
      body: JSON.stringify({ target_role: context.role, target_tenant_id: context.tenant_id }),
    });
    if (res.status === 401) { this.invalidateSession(); throw new Error('Sessão expirada.'); }
    if (!res.ok) throw new Error('Vínculo não autorizado ou indisponível.');
    this.user = serverUser(await res.json());
    this.notify();
    return this.user;
  }

  public invalidateSession(): void {
    this.clearSession();
    this.notify();
    if (typeof window !== 'undefined') window.dispatchEvent(new CustomEvent('frcaixinha:session-expired'));
  }

  public async logout(): Promise<void> {
    try {
      const headers: Record<string, string> = {
        'X-Requested-With': 'XMLHttpRequest',
      };
      if (this.token) {
        headers['Authorization'] = `Bearer ${this.token}`;
      }

      await fetch(`${getApiBaseUrl()}/api/v1/auth/logout`, {
        method: 'POST',
        headers,
        credentials: 'include',
      });
    } catch (e) {
      console.warn('Erro ao notificar logout ao servidor:', e);
    } finally {
      this.clearSession();
      this.notify();
    }
  }

  public async requestPasswordReset(email: string): Promise<{ success: boolean; message: string }> {
    const res = await fetch(`${getApiBaseUrl()}/api/auth/forgot-password`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email }),
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.message || data.error || 'Erro ao processar solicitação de recuperação.');
    }

    return data;
  }

  private armExpirationTimer(expiresAt: number) {
    if (this.expirationTimer) {
      clearTimeout(this.expirationTimer);
    }
    const delay = Math.max(0, expiresAt - Date.now());
    this.expirationTimer = window.setTimeout(() => {
      this.handleSessionExpired();
    }, delay);
  }

  private handleSessionExpired() {
    this.clearSession();
    this.notify();
    // Dispatch event to show toast or notification
    window.dispatchEvent(new CustomEvent('frcaixinha:session-expired'));
  }

  private clearSession() {
    this.token = null;
    this.user = null;
    this.expiresAt = null;
    if (this.expirationTimer) {
      clearTimeout(this.expirationTimer);
      this.expirationTimer = null;
    }
  }
}

export const authService = new AuthService();
