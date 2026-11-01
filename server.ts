import express, { Request, Response, NextFunction } from 'express';
import { createServer as createViteServer } from 'vite';
import crypto from 'crypto';

const app = express();
const PORT = 3000;

app.use(express.json());

// In-memory secure server session store (tokens are NEVER saved on client localStorage)
interface ServerSession {
  token: string;
  userId: string;
  role: 'MASTER' | 'TENANT_ADMIN' | 'TENANT_MEMBER';
  tenantId?: string;
  userName: string;
  userEmail: string;
  createdAt: number;
  expiresAt: number;
}

const activeSessions = new Map<string, ServerSession>();

// Secret key for HMAC token signing (server-only)
const SERVER_AUTH_SECRET = process.env.AUTH_SECRET || crypto.randomBytes(32).toString('hex');

// Contrato Técnico Mestre (Cláusulas 1.2, 14.1 e 16.2):
// O backend oficial especificado é FastAPI (Python) + PostgreSQL (RLS).
// Este servidor Express opera exclusivamente como scaffold de fronteira e roteamento local.
const IS_EXTERNAL_IDP_CONFIGURED = Boolean(
  process.env.DATABASE_URL ||
  process.env.FASTAPI_BACKEND_URL ||
  process.env.FIREBASE_CONFIG
);

// Helper to verify cryptographic session token
function verifySessionToken(token: string): boolean {
  try {
    const decoded = Buffer.from(token, 'base64url').toString('utf-8');
    const [payload, signature] = decoded.split('.');
    if (!payload || !signature) return false;
    const expected = crypto.createHmac('sha256', SERVER_AUTH_SECRET).update(payload).digest('hex');
    return crypto.timingSafeEqual(Buffer.from(signature), Buffer.from(expected));
  } catch {
    return false;
  }
}

// Authentication Middleware (Bloqueia sem token válido emitido pelo servidor)
interface AuthenticatedRequest extends Request {
  sessionUser?: ServerSession;
}

function requireAuth(req: AuthenticatedRequest, res: Response, next: NextFunction) {
  const authHeader = req.headers.authorization;
  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return res.status(401).json({
      error: 'Autenticação necessária',
      code: 'UNAUTHENTICATED',
      message: 'Token de autorização ausente ou malformado. Faça login para continuar.',
    });
  }

  const token = authHeader.split(' ')[1];
  if (!verifySessionToken(token)) {
    return res.status(401).json({
      error: 'Token inválido',
      code: 'INVALID_TOKEN',
      message: 'Token de assinatura inválido ou violado.',
    });
  }

  const session = activeSessions.get(token);
  if (!session) {
    return res.status(401).json({
      error: 'Sessão não encontrada ou revogada',
      code: 'SESSION_REVOKED',
      message: 'A sessão foi encerrada. Efetue um novo login.',
    });
  }

  if (Date.now() > session.expiresAt) {
    activeSessions.delete(token);
    return res.status(401).json({
      error: 'Sessão expirada',
      code: 'SESSION_EXPIRED',
      message: 'Sua sessão expirou por tempo de inatividade.',
    });
  }

  session.expiresAt = Date.now() + 15 * 60 * 1000;
  req.sessionUser = session;
  next();
}

// --- API ENDPOINTS ---

// Helper para encaminhamento reverso transparente e seguro ao FastAPI
async function forwardToFastAPI(req: Request, res: Response, targetPath?: string): Promise<boolean> {
  const backendBase = process.env.FASTAPI_BACKEND_URL;
  if (!backendBase) return false;

  // 1. Proteção CSRF para requisições de mutação com base em cookies
  if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(req.method)) {
    const hasBearer = Boolean(req.headers.authorization?.startsWith('Bearer '));
    const hasCustomHeader = Boolean(req.headers['x-requested-with'] || req.headers['x-frcaixinha-client']);
    const origin = req.headers.origin || req.headers.referer;
    const isAllowedOrigin = origin
      ? origin.includes('localhost') || origin.includes('127.0.0.1') || origin.includes('.run.app')
      : true;

    if (!hasBearer && !hasCustomHeader && !isAllowedOrigin) {
      res.status(403).json({
        error: 'Falha de Proteção CSRF',
        code: 'CSRF_REJECTED',
        message: 'Requisição bloqueada por política de proteção contra Cross-Site Request Forgery.',
      });
      return true;
    }
  }

  try {
    const targetUrl = `${backendBase.replace(/\/$/, '')}${targetPath || req.originalUrl}`;
    const headers: Record<string, string> = {};
    if (req.headers['content-type']) {
      headers['Content-Type'] = String(req.headers['content-type']);
    }
    if (req.headers.authorization) {
      headers['Authorization'] = String(req.headers.authorization);
    }
    if (req.headers.cookie) {
      headers['Cookie'] = String(req.headers.cookie);
    }
    headers['X-Forwarded-Host'] = req.headers.host || 'localhost:3000';
    headers['X-Forwarded-Proto'] = req.protocol || 'http';

    const response = await fetch(targetUrl, {
      method: req.method,
      headers,
      body: ['POST', 'PUT', 'PATCH'].includes(req.method) ? JSON.stringify(req.body) : undefined,
    });

    // 2. Propagação estrita de Set-Cookie do backend FastAPI para o navegador
    const setCookieHeaders = typeof response.headers.getSetCookie === 'function'
      ? response.headers.getSetCookie()
      : response.headers.get('set-cookie');

    if (setCookieHeaders && setCookieHeaders.length > 0) {
      res.setHeader('Set-Cookie', setCookieHeaders);
    }

    const contentType = response.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
      const data = await response.json();
      res.status(response.status).json(data);
    } else {
      const text = await response.text();
      res.status(response.status).send(text);
    }
    return true;
  } catch (err) {
    console.error(`[PROXY] Erro ao comunicar com FastAPI em ${backendBase}:`, err);
    res.status(502).json({
      error: 'Falha de Gateway com Backend Contratual',
      code: 'FASTAPI_GATEWAY_ERROR',
      message: 'Não foi possível conectar ao processo FastAPI. Verifique se o uvicorn está ativo.',
      detail: String(err),
    });
    return true;
  }
}

// 1. Status da Infraestrutura de Autenticação e Backend
app.get(['/api/auth/status', '/api/v1/auth/status'], async (req, res) => {
  // Se o backend FastAPI estiver configurado e ativo, consulta o status real dele
  if (process.env.FASTAPI_BACKEND_URL) {
    const handled = await forwardToFastAPI(req, res, '/api/v1/auth/status');
    if (handled) return;
  }

  res.json({
    status: 'BLOCKED_PENDING_CONFIG',
    configured: false,
    provider: 'NONE',
    architectureContract: 'FastAPI / PostgreSQL com RLS (Contrato Técnico Mestre)',
    scaffoldNote: 'Servidor Express em execução é scaffold transitório de fronteira. Autenticação oficial exige backend FastAPI / banco PostgreSQL conectado.',
    requiresAuthentication: true,
    message: 'Autenticação ainda não configurada. Nenhuma sessão foi iniciada.',
    serverTime: new Date().toISOString(),
  });
});

// 2. Login endpoint (Comportamento seguro com backend/IdP não configurado)
app.post(['/api/auth/login', '/api/v1/auth/login'], async (req, res) => {
  const { usernameOrEmail, password } = req.body;

  if (!usernameOrEmail || !password) {
    return res.status(400).json({
      error: 'Campos obrigatórios',
      message: 'Informe o e-mail/usuário e a senha de acesso.',
    });
  }

  // Encaminha requisição ao FastAPI quando a URL do backend estiver configurada
  if (process.env.FASTAPI_BACKEND_URL) {
    const handled = await forwardToFastAPI(req, res, '/api/v1/auth/login');
    if (handled) return;
  }

  // REGRA INVIOLÁVEL: Sem FastAPI / banco PostgreSQL de produção provisionado,
  // nenhuma sessão é criada e nenhum bypass é permitido.
  return res.status(503).json({
    error: 'Autenticação não configurada',
    code: 'AUTH_UNCONFIGURED',
    message: 'Autenticação ainda não configurada. Nenhuma sessão foi iniciada.',
    backendRequirement: 'FastAPI / PostgreSQL (Contrato Técnico Mestre)',
    detail: 'O backend contratual oficial (FastAPI/PostgreSQL) não está conectado a este container de desenvolvimento. Para proteger a integridade dos dados, nenhuma conta demo ou acesso não autenticado é admitido.',
  });
});

// 3. Obter sessão atual
app.get(['/api/auth/me', '/api/v1/auth/me'], async (req: AuthenticatedRequest, res) => {
  if (process.env.FASTAPI_BACKEND_URL) {
    const handled = await forwardToFastAPI(req, res, '/api/v1/auth/me');
    if (handled) return;
  }

  return requireAuth(req, res, () => {
    const session = req.sessionUser!;
    res.json({
      user: {
        id: session.userId,
        name: session.userName,
        email: session.userEmail,
        role: session.role,
        tenantId: session.tenantId,
      },
      expiresAt: session.expiresAt,
    });
  });
});

// 4. Logout endpoint (Invalida sessão de forma garantida no servidor)
app.post(['/api/auth/logout', '/api/v1/auth/logout'], (req, res) => {
  const authHeader = req.headers.authorization;
  if (authHeader && authHeader.startsWith('Bearer ')) {
    const token = authHeader.split(' ')[1];
    activeSessions.delete(token);
  }
  res.json({ success: true, message: 'Sessão encerrada com sucesso no servidor.' });
});

// 5. Recuperação de Senha Segura
app.post(['/api/auth/forgot-password', '/api/v1/auth/forgot-password'], (req, res) => {
  const { email } = req.body;
  if (!email || !String(email).includes('@')) {
    return res.status(400).json({
      error: 'E-mail inválido',
      message: 'Informe um endereço de e-mail válido.',
    });
  }

  console.log(`[AUDIT-AUTH] Solicitação de recuperação de senha: ${email} em ${new Date().toISOString()}`);

  if (!IS_EXTERNAL_IDP_CONFIGURED) {
    return res.status(503).json({
      error: 'Serviço não configurado',
      message: 'Serviço de envio de e-mails de recuperação não configurado.',
    });
  }

  res.json({
    success: true,
    message: 'Se o e-mail estiver cadastrado no sistema, as instruções foram despachadas.',
  });
});

// 6. Tenant Data Endpoint com Isolamento Estrito de RBAC
app.get('/api/tenants/:tenantId/data', requireAuth, (req: AuthenticatedRequest, res) => {
  const session = req.sessionUser!;
  const targetTenantId = req.params.tenantId;

  // REGRA 1: MASTER NÃO ACESSA DADOS FINANCEIROS E MEMBROS DO TENANT
  if (session.role === 'MASTER') {
    return res.status(403).json({
      error: 'Acesso Proibido ao Master',
      code: 'MASTER_FINANCIAL_RESTRICTION',
      message: 'O perfil Master gerencia apenas licenças, precificação global e suporte auditado. É proibido o acesso a saldos, membros ou dados bancários/financeiros da caixinha (Cláusula 2.8 de Segregação Patrimonial e LGPD).',
    });
  }

  // REGRA 2: ADMIN SÓ ACESSA SEU PRÓPRIO TENANT
  if (session.role === 'TENANT_ADMIN' && session.tenantId !== targetTenantId) {
    return res.status(403).json({
      error: 'Isolamento Multi-Inquilino Violado',
      code: 'CROSS_TENANT_ACCESS_DENIED',
      message: `Você é administrador do tenant '${session.tenantId}' e não possui permissão para acessar os dados do tenant '${targetTenantId}'.`,
    });
  }

  // REGRA 3: MEMBRO SÓ ACESSA SEU PRÓPRIO TENANT
  if (session.role === 'TENANT_MEMBER' && session.tenantId !== targetTenantId) {
    return res.status(403).json({
      error: 'Acesso Negado a Outra Caixinha',
      code: 'MEMBER_WRONG_TENANT',
      message: 'Você não é membro desta caixinha.',
    });
  }

  res.json({
    authorized: true,
    tenantId: targetTenantId,
    actorRole: session.role,
    actorUserId: session.userId,
    timestamp: new Date().toISOString(),
  });
});

// 6.1. Encaminhamento e Bloqueio de Operações Financeiras (/api/v1/tenants/:tenantId/*)
app.all(['/api/v1/tenants/:tenantId/*', '/api/tenants/:tenantId/*'], async (req: AuthenticatedRequest, res) => {
  // Se o backend FastAPI estiver ativo, encaminha de forma transparente e segura
  if (process.env.FASTAPI_BACKEND_URL) {
    const handled = await forwardToFastAPI(req, res);
    if (handled) return;
  }

  // Se for simulação matemática pura da Tabela Price (cálculo sem estado)
  if (req.path.includes('/loans/simulate') && req.method === 'POST') {
    const { principal, term_months, monthly_rate = 0.20 } = req.body;
    const P = Number(principal) || 0;
    const n = Number(term_months) || 1;
    const i = Number(monthly_rate);
    const factor = Math.pow(1.0 + i, -n);
    const pmt = Math.round(P * (i / (1.0 - factor)) * 100) / 100;
    return res.json({
      principal: P,
      monthly_rate: i,
      term_months: n,
      uniform_payment: pmt,
      last_payment: pmt,
      total_interest: Math.round((pmt * n - P) * 100) / 100,
      total_payable: Math.round(pmt * n * 100) / 100,
      is_irregular_first_period: false,
      schedule: []
    });
  }

  // REGRA INVIOLÁVEL: Sem o backend FastAPI e banco PostgreSQL conectados,
  // nenhuma operação financeira é admitida ou gravada localmente.
  return res.status(503).json({
    error: 'Operação Financeira Bloqueada',
    code: 'FASTAPI_BACKEND_UNAVAILABLE',
    message: 'O backend oficial FastAPI/PostgreSQL não está conectado neste ambiente. Operações financeiras requerem persistência transacional autoritativa no servidor (Contrato Técnico Mestre).',
    detail: 'Para proteção patrimonial e segregação por RLS, é expressamente vedada a persistência de saldos, cotas, amortizações ou liquidações em armazenamento local ou fallback fictício.'
  });
});

// 7. Master-only endpoint para licenças
app.get('/api/master/licenses', requireAuth, (req: AuthenticatedRequest, res) => {
  const session = req.sessionUser!;
  if (session.role !== 'MASTER') {
    return res.status(403).json({
      error: 'Apenas Master',
      code: 'MASTER_ONLY',
      message: 'Apenas o Administrador Master pode gerenciar planos e precificação da plataforma.',
    });
  }

  res.json({
    authorized: true,
    message: 'Acesso autorizado ao painel de precificação SaaS.',
  });
});

// 8. Health check
app.get('/api/health', (_req, res) => {
  res.json({
    status: 'ONLINE',
    app: 'FRcaixinha 2.2',
    timestamp: new Date().toISOString(),
    backendContract: 'FastAPI / PostgreSQL (Contrato Técnico Mestre)',
    scaffoldStatus: 'Interim Node/Express API Boundary',
    authConfigured: IS_EXTERNAL_IDP_CONFIGURED,
  });
});

// Start Express server and mount Vite middleware in development
async function startServer() {
  const vite = await createViteServer({
    server: {
      middlewareMode: true,
      hmr: false,
      watch: null,
    },
    appType: 'spa',
  });

  app.use(vite.middlewares);

  const server = app.listen(PORT, '0.0.0.0', () => {
    console.log(`[FRcaixinha 2.2] Servidor de Fronteira API ativo em http://0.0.0.0:${PORT}`);
  });

  const cleanup = () => {
    server.close(() => {
      process.exit(0);
    });
  };
  process.on('SIGTERM', cleanup);
  process.on('SIGINT', cleanup);
}

startServer();
