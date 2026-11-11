/**
 * FRcaixinha AI Studio Mobile - Serviço de Autenticação com Fronteira de Servidor Real
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

/** Identifica uma sessão específica sem persistir tokens ou fornecer permissão. */
export interface AuthSessionSnapshot {
  readonly token: string | null;
  readonly generation: number;
}

import {parseServerSessionInventory} from './sessionInventory';
import {classifyApiOrigin} from './apiOriginPolicy';

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
    if (!item || typeof item !== 'object' || Array.isArray(item))
      throw new Error('Vínculo inválido.');
    const raw = item as Record<string, unknown>;
    if (Object.keys(raw).some(key => !['role','tenant_id','tenant_name'].includes(key)))
      throw new Error('O servidor retornou campos não autorizados no vínculo.');
    const role = raw.role;
    const tenantId = raw.tenant_id;
    const tenantName = raw.tenant_name;
    if (typeof role !== 'string' ||
        !['MASTER', 'TENANT_ADMIN', 'TENANT_MEMBER'].includes(role)) {
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
    const key = role + ':' + String(tenantId ?? '').toLowerCase();
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
  const declared = (import.meta as any).env?.VITE_API_URL;
  return classifyApiOrigin(declared).origin;
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
  private loginInProgress = false;

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

  /** Requisições devem descartar resultados caso o login mude enquanto aguardam rede. */
  public captureSession(): AuthSessionSnapshot {
    const token = this.getToken();
    return { token, generation: this.sessionGeneration };
  }

  public isSessionSnapshotCurrent(snapshot: AuthSessionSnapshot): boolean {
    if (!snapshot.token || snapshot.token !== this.token ||
        snapshot.generation !== this.sessionGeneration) return false;
    return this.isAuthenticated();
  }

  /** Um 401 antigo nunca deve encerrar um login novo. */
  public invalidateSessionIfCurrent(snapshot: AuthSessionSnapshot): boolean {
    if (!this.isSessionSnapshotCurrent(snapshot)) return false;
    this.invalidateSession();
    return true;
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
        const refreshed = serverUser(data.user || data);
        if (refreshed.id !== this.user?.id ||
            refreshed.role !== this.user?.role ||
            (refreshed.tenantId ?? null) !== (this.user?.tenantId ?? null)) {
          this.invalidateSession();
          return null;
        }
        this.user = refreshed;
        this.expiresAt = expiration;
        this.armExpirationTimer(expiration);
        this.notify();
        return this.user;
      }
      this.invalidateSessionIfCurrent({token: originalToken, generation});
      return null;
    } catch {
      if (generation === this.sessionGeneration && originalToken === this.token) {
        this.clearSession();
        this.notify();
      }
      return null;
    }
  }

  public async login(usernameOrEmail: string, password: string, requestedRole?: AuthenticatedUser['role'], requestedTenantId?: string): Promise<AuthenticatedUser> {
    if (this.loginInProgress) throw new Error('Outra tentativa de login está em andamento.');
    this.loginInProgress = true;
    try {
      return await this.performLogin(usernameOrEmail, password, requestedRole, requestedTenantId);
    } finally {
      this.loginInProgress = false;
    }
  }

  /** Revogação best-effort de token que não chegou a ser aceito no cliente. */
  private async revokeUnusedLoginToken(token: unknown): Promise<void> {
    if (typeof token !== 'string' || !token) return;
    try {
      await fetch(getApiBaseUrl() + '/api/v1/auth/logout', {
        method: 'POST',
        headers: {
          'Authorization': 'Bearer ' + token,
          'X-Requested-With': 'XMLHttpRequest',
          'Cache-Control': 'no-store',
        },
        credentials: 'include',
        cache: 'no-store',
      });
    } catch {
      // Sem conexão, o token permanece inacessível no cliente; TTL no servidor.
    }
  }

  private async performLogin(usernameOrEmail: string, password: string, requestedRole?: AuthenticatedUser['role'], requestedTenantId?: string): Promise<AuthenticatedUser> {
    if (this.isAuthenticated()) {
      throw new Error('Saia da conta antes de entrar em outro perfil.');
    }
    if (requestedTenantId && (!requestedRole || requestedRole === 'MASTER' ||
        !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(requestedTenantId))) {
      throw new Error('Perfil e identificador da caixinha precisam ser validos.');
    }
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
      body: JSON.stringify({ usernameOrEmail, password, requestedRole, requestedTenantId }),
    });

    const data = await res.json();
    if (generation !== this.sessionGeneration) {
      if (res.ok) await this.revokeUnusedLoginToken(data?.token);
      throw new Error('Operação de login cancelada: a sessão foi alterada.');
    }
    if (!res.ok) {
      throw new Error(data.detail || data.message || data.error || 'Falha ao autenticar.');
    }

    // Armazenamento EXCLUSIVO em memória (RAM transitória)
    const expiresAt = data.expiresAt ?? Date.parse(data.expires_at);
    if (!data.token || !Number.isFinite(expiresAt) || expiresAt <= Date.now()) throw new Error('Sessão inválida recebida do servidor.');
    let authenticated: AuthenticatedUser;
    try {
      authenticated = serverUser(data.user);
    } catch {
      await this.revokeUnusedLoginToken(data.token);
      throw new Error('Resposta de identidade inválida.');
    }
    if ((requestedRole && authenticated.role !== requestedRole) ||
        (requestedTenantId && (authenticated.tenantId ?? '').toLowerCase() !== requestedTenantId.toLowerCase()) ||
        (authenticated.role === 'MASTER' &&
         (requestedRole !== 'MASTER' || (authenticated.tenantId ?? null) !== null))) {
      await this.revokeUnusedLoginToken(data.token);
      throw new Error('O servidor não confirmou o perfil de acesso solicitado.');
    }
    // Nao anunciar sessão MASTER antes da verificação server-side.
    if (authenticated.role === 'MASTER') {
      let confirmed = false;
      try {
        const proof = await fetch(getApiBaseUrl() + '/api/v1/master/owner-access', {
          method: 'GET',
          headers: {
            'Authorization': 'Bearer ' + data.token,
            'X-Requested-With': 'XMLHttpRequest',
            'Cache-Control': 'no-store',
          },
          credentials: 'include',
          cache: 'no-store',
        });
        if (proof.ok) {
          const result = await proof.json();
          confirmed = result?.verified === true &&
            result?.role === 'MASTER' &&
            result?.scope === 'PLATFORM_GOVERNANCE_ONLY' &&
            (authenticated.tenantId ?? null) === null;
        }
      } catch {
        // Falha fechada: nao promover sessao Master.
      }
      if (!confirmed || generation !== this.sessionGeneration) {
        await this.revokeUnusedLoginToken(data.token);
        throw new Error('Acesso do proprietário não confirmado pelo servidor.');
      }
    }
    if (generation !== this.sessionGeneration) {
      await this.revokeUnusedLoginToken(data.token);
      throw new Error('Operação de login cancelada: a sessão foi alterada.');
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
    const contexts = parseServerContexts(raw);
    // /contexts é apenas da sessão atual. Não revelar outras caixinhas ou
    // outros papéis a partir de um payload atrasado ou não autorizado.
    if (!this.user || contexts.length !== 1 ||
        contexts[0].role !== this.user.role ||
        (contexts[0].tenant_id ?? null) !== (this.user.tenantId ?? null)) {
      throw new Error('O servidor não confirmou exclusivamente o vínculo autenticado.');
    }
    return contexts;
  }

  public async listSessions(): Promise<UserSessionInfo[]> {
    if (!this.isAuthenticated()) throw new Error('Sessão expirada.');
    const snapshot=this.captureSession();
    const expected=this.getUser();
    if(!expected||!snapshot.token)throw new Error('Sessão expirada.');
    const result=await fetch(getApiBaseUrl()+'/api/v1/auth/sessions',{
      headers:{'Authorization':'Bearer '+snapshot.token,'Cache-Control':'no-store'},
      cache:'no-store',
    });
    if(!this.isSessionSnapshotCurrent(snapshot))return [];
    if(result.status===401){this.invalidateSessionIfCurrent(snapshot);throw new Error('Sessão expirada.');}
    if(!result.ok)throw new Error('Sessões indisponíveis.');
    const raw:unknown=await result.json();
    if(!this.isSessionSnapshotCurrent(snapshot))return [];
    const rows=parseServerSessionInventory(raw,expected);
    if(!this.isSessionSnapshotCurrent(snapshot))return [];
    return rows;
  }

  public async revokeSession(sessionId: string): Promise<boolean> {
    if (!this.isAuthenticated())throw new Error('Sessão expirada.');
    if(!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(sessionId))
      throw new Error('ID de sessão inválido.');
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
    if(generation!==this.sessionGeneration || token!==this.token)
      throw new Error('Sessão alterada durante revogação.');
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
    const normalized = email.trim().toLowerCase();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(normalized) || normalized.length > 254) {
      throw new Error('Informe um e-mail válido.');
    }
    const baseUrl = getApiBaseUrl();
    if (!baseUrl) throw new Error('Servidor FR Finance indisponível.');
    const res = await fetch(`${baseUrl}/api/v1/auth/forgot-password`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      cache: 'no-store',
      body: JSON.stringify({ email: normalized }),
    });
    let data: unknown;
    try { data = await res.json(); } catch { data = null; }
    const reply = (data && typeof data === 'object' && !Array.isArray(data))
      ? data as Record<string, unknown> : {};
    if (!res.ok) {
      // Do not surface raw backend error bodies or returned emails/tokens.
      if (res.status === 429) throw new Error('Muitas solicitações. Tente mais tarde.');
      throw new Error('Recuperação ainda indisponível. Nenhuma mensagem foi enviada.');
    }
    if (res.status !== 202 ||
        reply.status !== 'REQUEST_ACCEPTED_IF_ELIGIBLE' ||
        reply.user_exists !== null || reply.email_sent !== false ||
        typeof reply.message !== 'string') {
      throw new Error('Servidor não comprovou o registro da solicitação.');
    }
    return {success: true, message: reply.message};
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
