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
  tenant_name?: string | null;
}

export interface UserSessionInfo {
  id: string;
  role: AuthenticatedUser['role'];
  tenant_id: string | null;
  created_at: string;
  expires_at: string;
  current: boolean;
}

/** O servidor decide qual vínculo existe; nunca confiar no texto de um <select>. */
export function parseServerContexts(value: unknown): AuthContext[] {
  if (!Array.isArray(value) || value.length > 200) throw new Error('Lista de vínculos inválida.');
  const result: AuthContext[] = [];
  const seen = new Set<string>();
  for (const item of value) {
    if (!item || typeof item !== 'object') throw new Error('Vínculo inválido.');
    const role = (item as Record<string, unknown>).role;
    const tenantId = (item as Record<string, unknown>).tenant_id;
    const tenantName = (item as Record<string, unknown>).tenant_name;
    if (!['MASTER', 'TENANT_ADMIN', 'TENANT_MEMBER'].includes(String(role))) {
      throw new Error('Papel inválido recebido do servidor.');
    }
    if (role === 'MASTER') {
      if (tenantId !== null || (tenantName !== undefined && tenantName !== null))
        throw new Error('O Master não pertence a uma caixinha por este perfil.');
    } else if (typeof tenantId !== 'string' ||
        !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(tenantId)) {
      throw new Error('Identificador da caixinha inválido.');
    }
    if (role !== 'MASTER' && tenantName !== undefined && tenantName !== null &&
        (typeof tenantName !== 'string' || tenantName.trim().length < 1 ||
         tenantName.length > 255 || /[\u0000-\u001f\u007f]/.test(tenantName))) {
      throw new Error('Nome da caixinha inválido.');
    }
    const key = String(role) + ':' + String(tenantId ?? '');
    if (seen.has(key)) throw new Error('Vínculo duplicado na resposta.');
    seen.add(key);
    result.push({
      role: role as AuthenticatedUser['role'],
      tenant_id: tenantId as string | null,
      tenant_name: typeof tenantName === 'string' ? tenantName.trim() : null,
    });
  }
  return result;
}

export function contextLabel(context: AuthContext): string {
  if (context.role === 'MASTER') return 'Administrador Master — Plataforma';
  const label = context.role === 'TENANT_ADMIN' ? 'Administrador' : 'Membro';
  const tenant = context.tenant_name?.trim() ||
    ('Caixinha ' + (context.tenant_id || '').slice(0, 8).toUpperCase());
  return label + ' — ' + tenant;
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
    const candidate = envUrl.trim().replace(/\/$/, '');
    try {
      const parsed = new URL(candidate);
      // HTTP somente no loopback; acesso remoto exige HTTPS.
      if (parsed.protocol === 'https:' ||
          (parsed.protocol === 'http:' && ['127.0.0.1', 'localhost', '[::1]'].includes(parsed.hostname))) {
        return candidate;
      }
    } catch { /* URL inválida: bloqueio seguro. */ }
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
  private sessionGeneration = 0;

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
    const originalToken = this.token;
    const generation = this.sessionGeneration;

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

      if (generation !== this.sessionGeneration || originalToken !== this.token) {
        return null; // Logout ou troca de sessão enquanto o GET estava pendente.
      }
      if (!res.ok) {
        this.clearSession();
        this.notify();
        return null;
      }

      const data = await res.json();
      if (generation !== this.sessionGeneration || originalToken !== this.token) return null;
      if (data && (data.user || data.id)) {
        // /me não retorna TTL. Não prorrogar indefinidamente a validade
        // local, que deve continuar limitada ao token original do login.
        const candidateExpiration = data.expiresAt
          ? (typeof data.expiresAt === 'number' ? data.expiresAt : Date.parse(data.expiresAt))
          : this.expiresAt;
        const expiration = Math.min(this.expiresAt ?? 0, candidateExpiration ?? 0);
        if (!Number.isFinite(expiration) || expiration <= Date.now()) {
          this.invalidateSession();
          return null;
        }
        this.user = serverUser(data.user || data);
        this.expiresAt = expiration;
        this.armExpirationTimer(expiration);
        this.notify();
        return this.user;
      }
      return null;
    } catch {
      if (generation === this.sessionGeneration && originalToken === this.token) {
        this.clearSession();
        this.notify();
      }
      return null;
    }
  }

  public async login(usernameOrEmail: string, password: string, requestedRole?: AuthenticatedUser['role']): Promise<AuthenticatedUser> {
    if (isNativeMobilePlatform() && !getApiBaseUrl()) {
      throw new Error('Servidor backend móvel não configurado. Defina VITE_API_URL apontando para a API FastAPI antes de gerar o APK.');
    }

    const generation = this.sessionGeneration;
    const res = await fetch(`${getApiBaseUrl()}/api/v1/auth/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
      },
      credentials: 'include',
      body: JSON.stringify({ usernameOrEmail, password, requestedRole }),
    });

    const data = await res.json();
    if (generation !== this.sessionGeneration) {
      throw new Error('Operação de login cancelada: a sessão foi alterada.');
    }
    if (!res.ok) {
      throw new Error(data.detail || data.message || data.error || 'Falha ao autenticar.');
    }

    // Armazenamento EXCLUSIVO em memória (RAM transitória)
    const expiresAt = data.expiresAt ?? Date.parse(data.expires_at);
    if (!data.token || !Number.isFinite(expiresAt) || expiresAt <= Date.now()) throw new Error('Sessão inválida recebida do servidor.');
    const authenticated = serverUser(data.user);
    if (requestedRole && authenticated.role !== requestedRole) {
      throw new Error('O servidor não confirmou o perfil de acesso solicitado.');
    }
    this.token = data.token;
    this.user = authenticated;
    this.expiresAt = expiresAt;
    this.sessionGeneration++;

    this.armExpirationTimer(expiresAt);
    this.notify();

    return this.user!;
  }

  public async listContexts(): Promise<AuthContext[]> {
    if (!this.isAuthenticated()) return [];
    const token = this.token;
    const generation = this.sessionGeneration;
    const res = await fetch(getApiBaseUrl() + '/api/v1/auth/contexts', {
      headers: { Authorization: 'Bearer ' + token, 'Cache-Control': 'no-store' },
    });
    if (generation !== this.sessionGeneration || token !== this.token) return [];
    if (res.status === 401) { this.invalidateSession(); return []; }
    if (!res.ok) throw new Error('Não foi possível consultar os vínculos.');
    const raw = await res.json();
    if (generation !== this.sessionGeneration || token !== this.token) return [];
    return parseServerContexts(raw);
  }

  public async listSessions(): Promise<UserSessionInfo[]> {
    if (!this.isAuthenticated()) throw new Error('Sessão expirada.');
    const token=this.token, generation=this.sessionGeneration;
    const result=await fetch(getApiBaseUrl()+'/api/v1/auth/sessions',{
      headers:{'Authorization':'Bearer '+token,'Cache-Control':'no-store'},
    });
    if (generation!==this.sessionGeneration || token!==this.token) return [];
    if(result.status===401){this.invalidateSession();throw new Error('Sessão expirada.');}
    if(!result.ok)throw new Error('Sessões indisponíveis.');
    const data=await result.json();
    if (generation!==this.sessionGeneration || token!==this.token) return [];
    if(data?.source!=='POSTGRESQL_AUTH'||!Array.isArray(data.sessions)||
       data.sessions.length>100)throw new Error('Lista de sessões inválida.');
    return data.sessions.map((item:any)=>{
      if(typeof item?.id!=='string'||!(/^[0-9a-f-]{36}$/i.test(item.id))||
         !['MASTER','TENANT_ADMIN','TENANT_MEMBER'].includes(item.role)||
         !Number.isFinite(Date.parse(item.created_at))||
         !Number.isFinite(Date.parse(item.expires_at))||
         typeof item.current!=='boolean')throw new Error('Sessão inválida.');
      return {
        id:item.id,role:item.role,tenant_id:item.tenant_id??null,
        created_at:item.created_at,expires_at:item.expires_at,current:item.current,
      } as UserSessionInfo;
    });
  }

  public async revokeSession(sessionId: string): Promise<boolean> {
    if (!this.isAuthenticated())throw new Error('Sessão expirada.');
    if(!/^[0-9a-f-]{36}$/i.test(sessionId))throw new Error('ID de sessão inválido.');
    const token=this.token,generation=this.sessionGeneration;
    const result=await fetch(
      getApiBaseUrl()+'/api/v1/auth/sessions/'+encodeURIComponent(sessionId)+'/revoke',{
        method:'POST',headers:{'Authorization':'Bearer '+token,
          'X-Requested-With':'XMLHttpRequest','Cache-Control':'no-store'},
      });
    if(generation!==this.sessionGeneration || token!==this.token)
      throw new Error('Sessão alterada durante revogação.');
    if(result.status===401){this.invalidateSession();throw new Error('Sessão expirada.');}
    if(!result.ok)throw new Error('Não foi possível revogar a sessão.');
    const data=await result.json();
    if(data?.success!==true || data?.session_id!==sessionId ||
       typeof data?.current_revoked!=='boolean')throw new Error('Resposta inválida.');
    if(data.current_revoked)this.invalidateSession();
    return data.current_revoked;
  }

  /** Troca entre Master, Admin e Membro proibida dentro da mesma sessao. */
  public async switchContext(_context: AuthContext): Promise<AuthenticatedUser> {
    throw new Error('Saia da conta e entre novamente para acessar outro perfil.');
  }

  public invalidateSession(): void {
    this.clearSession();
    this.notify();
    if (typeof window !== 'undefined') window.dispatchEvent(new CustomEvent('frcaixinha:session-expired'));
  }

  public async logout(): Promise<void> {
    // Primeiro revoga LOCALMENTE, sem esperar rede. Uma resposta tardia da
    // sessão antiga não pode ressuscitar o perfil nem apagar novo login.
    const token = this.token;
    this.clearSession();
    this.notify();
    if (!token) return;
    try {
      await fetch(`${getApiBaseUrl()}/api/v1/auth/logout`, {
        method: 'POST',
        headers: {
          'X-Requested-With': 'XMLHttpRequest',
          'Authorization': `Bearer ${token}`,
          'Cache-Control': 'no-store',
        },
        credentials: 'include',
      });
    } catch {
      // Sessão já está encerrada no cliente; backend pode ter ficado
      // indisponível. Nunca reativar acesso local.
    }
  }

  public async requestPasswordReset(email: string): Promise<{ success: boolean; message: string }> {
    const res = await fetch(`${getApiBaseUrl()}/api/v1/auth/forgot-password`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email }),
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || data.message || data.error || 'Recuperação de senha indisponível.');
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
    this.sessionGeneration++;
    if (this.expirationTimer) {
      clearTimeout(this.expirationTimer);
      this.expirationTimer = null;
    }
  }
}

export const authService = new AuthService();
