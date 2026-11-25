/**
 * M41040 — roteiro de adesão para a primeira caixinha do proprietário.
 *
 * This is a frozen, source-only checklist. It does not send invitations, create
 * accounts or cycles, record consent, charge SaaS, or collect quota payments.
 * Requirement IDs refer to the existing 330-item matrix; none is promoted here.
 */
export type FirstCaixinhaOnboardingStepIdV1 =
  | "MASTER_INVITES_ADMIN"
  | "ADMIN_REGISTERS"
  | "ADMIN_ACCEPTS_CONTRACT_A"
  | "ADMIN_PAYS_SAAS"
  | "ADMIN_CONFIGURES_AND_ACCEPTS_CONTRACT_B"
  | "ADMIN_INVITES_MEMBERS"
  | "MEMBERS_REGISTER_AND_ACCEPT_CONTRACT_B"
  | "MEMBERS_PAY_CONTRIBUTIONS"
  | "ADMIN_CLOSES_CYCLE";

export interface FirstCaixinhaOnboardingStepV1 {
  readonly id: FirstCaixinhaOnboardingStepIdV1;
  readonly actor: string;
  readonly title: string;
  readonly description: string;
  readonly blocker: string;
  readonly requirementIds: readonly string[];
  readonly releaseGateIds: readonly string[];
  readonly pendingTaskIds: readonly string[];
  readonly status: "BLOCKED_SOURCE_ONLY";
  readonly actionEnabled: false;
  readonly acceptanceRecorded: false;
  readonly persisted: false;
}

export const FIRST_CAIXINHA_REQUIREMENT_STAGES_V1 = Object.freeze([
  "01_SCOPE",
  "02_CODE",
  "03_UNIT",
  "04_SECURITY",
  "05_E2E",
  "06_EXTERNAL",
  "07_SIGNOFF",
] as const);

type StepInput = Omit<
  FirstCaixinhaOnboardingStepV1,
  "status" | "actionEnabled" | "acceptanceRecorded" | "persisted"
>;

function frozenStep(input: StepInput): FirstCaixinhaOnboardingStepV1 {
  return Object.freeze({
    ...input,
    requirementIds: Object.freeze([...input.requirementIds]),
    releaseGateIds: Object.freeze([...input.releaseGateIds]),
    pendingTaskIds: Object.freeze([...input.pendingTaskIds]),
    status: "BLOCKED_SOURCE_ONLY" as const,
    actionEnabled: false as const,
    acceptanceRecorded: false as const,
    persisted: false as const,
  });
}

/** Business order requested by the owner, separated into SaaS and cashbox flows. */
export const FIRST_CAIXINHA_ONBOARDING_SEQUENCE_V1:
  readonly FirstCaixinhaOnboardingStepV1[] = Object.freeze([
    frozenStep({
      id: "MASTER_INVITES_ADMIN",
      actor: "Master",
      title: "Convidar o administrador",
      description: "Preparar e enviar um convite individual para iniciar o acesso do administrador da caixinha.",
      blocker: "Convite real segue bloqueado até MFA do Master, dupla aprovação, controle transacional do convite e entrega/verificação de e-mail.",
      requirementIds: ["CP26-0018", "CP26-0019", "CP26-0020", "CP26-0024"],
      releaseGateIds: ["AUTH_PRODUCTION", "MASTER_MFA", "DUAL_CONTROL", "TENANT_RLS", "INVITE_TRANSACTION", "VERIFIED_EMAIL", "MAIL_OUTBOX"],
      pendingTaskIds: [],
    }),
    frozenStep({
      id: "ADMIN_REGISTERS",
      actor: "Administrador convidado",
      title: "Cadastrar a conta e verificar a identidade",
      description: "Abrir o convite, fazer o cadastro individual e confirmar identidade, sessão e e-mail.",
      blocker: "Cadastro real depende da liberação de produção, identidade/e-mail verificados, recuperação segura de senha e isolamento por papel e tenant.",
      requirementIds: ["CP26-0018", "CP26-0019", "CP26-0020", "CP26-0024"],
      releaseGateIds: ["AUTH_PRODUCTION", "MASTER_MFA", "TENANT_RLS", "VERIFIED_EMAIL", "PASSWORD_RECOVERY"],
      pendingTaskIds: [],
    }),
    frozenStep({
      id: "ADMIN_ACCEPTS_CONTRACT_A",
      actor: "Administrador",
      title: "Revisar e aceitar o Contrato A da licença SaaS",
      description: "Conferir a versão canônica, os termos da licença e registrar o aceite expresso antes da contratação.",
      blocker: "O Contrato A permanece minuta; publicação canônica, revisão necessária e prova de consentimento ainda não foram homologadas.",
      requirementIds: ["CP26-0019", "CP26-0020", "CP26-0024"],
      releaseGateIds: ["AUTH_PRODUCTION", "CANONICAL_CONTRACT", "CONTRACT_CONSENT"],
      pendingTaskIds: ["LEGAL_LGPD_REGULATORY"],
    }),
    frozenStep({
      id: "ADMIN_PAYS_SAAS",
      actor: "Administrador",
      title: "Pagar a licença SaaS",
      description: "Pagar a licença da plataforma ao caixa Master, em operação separada das contribuições da caixinha.",
      blocker: "Oferta, autorização do provedor e conciliação independente ainda não estão liberadas; pagamentos reais permanecem OFF.",
      requirementIds: ["CP26-0006", "CP26-0023", "CP26-0024"],
      releaseGateIds: ["AUTH_PRODUCTION", "MP_CONNECT", "FINANCIAL_RECONCILIATION"],
      pendingTaskIds: ["MERCADO_PAGO_EXTERNAL_APPROVAL"],
    }),
    frozenStep({
      id: "ADMIN_CONFIGURES_AND_ACCEPTS_CONTRACT_B",
      actor: "Administrador da caixinha",
      title: "Configurar a caixinha e aceitar o Contrato B",
      description: "Definir os valores e as cotas da própria caixinha, conferir o calendário individual e aceitar os termos antes de solicitar a abertura.",
      blocker: "Contrato B e consentimento seguem pendentes; abertura exige autorização própria, e o corte do Capital-Dias ainda não foi decidido.",
      requirementIds: ["CP26-0007", "CP26-0010", "CP26-0011", "CP26-0019", "CP26-0020", "CP26-0024"],
      releaseGateIds: ["AUTH_PRODUCTION", "TENANT_RLS", "CANONICAL_CONTRACT", "CONTRACT_CONSENT"],
      pendingTaskIds: ["LEGAL_LGPD_REGULATORY"],
    }),
    frozenStep({
      id: "ADMIN_INVITES_MEMBERS",
      actor: "Administrador da caixinha",
      title: "Convidar os membros",
      description: "Enviar convites individuais somente depois da configuração e da adesão do administrador.",
      blocker: "Emissão e entrega reais dependem de convite transacional, e-mail verificado, isolamento do tenant e liberação formal da conta.",
      requirementIds: ["CP26-0018", "CP26-0019", "CP26-0020", "CP26-0024"],
      releaseGateIds: ["AUTH_PRODUCTION", "TENANT_RLS", "INVITE_TRANSACTION", "VERIFIED_EMAIL", "MAIL_OUTBOX"],
      pendingTaskIds: [],
    }),
    frozenStep({
      id: "MEMBERS_REGISTER_AND_ACCEPT_CONTRACT_B",
      actor: "Membro convidado",
      title: "Cadastrar-se e aceitar o Contrato B",
      description: "Cada membro usa seu próprio convite, confirma a identidade/e-mail e revisa os termos da caixinha antes de ingressar.",
      blocker: "Cadastro, consentimento versionado e segregação Master/Administrador/Membro ainda não têm homologação E2E em staging.",
      requirementIds: ["CP26-0018", "CP26-0019", "CP26-0020", "CP26-0024"],
      releaseGateIds: ["AUTH_PRODUCTION", "TENANT_RLS", "VERIFIED_EMAIL", "CANONICAL_CONTRACT", "CONTRACT_CONSENT", "PASSWORD_RECOVERY"],
      pendingTaskIds: ["LEGAL_LGPD_REGULATORY"],
    }),
    frozenStep({
      id: "MEMBERS_PAY_CONTRIBUTIONS",
      actor: "Membros",
      title: "Pagar as cotas da caixinha",
      description: "Depois do aceite, cada membro paga conforme valores escolhidos pelo administrador e instruções válidas da própria caixinha.",
      blocker: "Provedor, conciliação por tenant e testes externos estão pendentes; PIX_REAL e PAGAMENTOS_REAIS continuam OFF.",
      requirementIds: ["CP26-0007", "CP26-0010", "CP26-0023", "CP26-0024"],
      releaseGateIds: ["AUTH_PRODUCTION", "TENANT_RLS", "MP_CONNECT", "PIX_INBOUND", "FINANCIAL_RECONCILIATION"],
      pendingTaskIds: ["MERCADO_PAGO_EXTERNAL_APPROVAL"],
    }),
    frozenStep({
      id: "ADMIN_CLOSES_CYCLE",
      actor: "Administrador da caixinha",
      title: "Conciliar e encerrar o ciclo",
      description: "Conferir os registros e as obrigações para o encerramento planejado em 20/12/2027.",
      blocker: "Fechamento e pagamentos permanecem bloqueados até conciliação, política contratual aprovada, corte do Capital-Dias decidido e provas independentes.",
      requirementIds: ["CP26-0007", "CP26-0017", "CP26-0023", "CP26-0024"],
      releaseGateIds: ["AUTH_PRODUCTION", "TENANT_RLS", "FINANCIAL_RECONCILIATION", "ANNUAL_CLOSING"],
      pendingTaskIds: ["LEGAL_LGPD_REGULATORY"],
    }),
  ]);
