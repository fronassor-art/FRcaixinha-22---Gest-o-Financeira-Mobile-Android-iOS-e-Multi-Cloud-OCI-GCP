import React, { useState } from 'react';
import { X, BookOpen, CheckCircle, ChevronRight, Shield, Award, HelpCircle, FileText } from 'lucide-react';

interface AdminManualModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const AdminManualModal: React.FC<AdminManualModalProps> = ({ isOpen, onClose }) => {
  const [activeStep, setActiveStep] = useState(1);

  if (!isOpen) return null;

  const MANUAL_STEPS = [
    {
      num: 1,
      title: 'Criar Conta e Identidade Pessoal',
      objective: 'Cadastrar administrador responsável (Pessoa Física ou Jurídica).',
      screen: 'Cadastro Contratante PF/PJ',
      fields: 'Nome completo, CPF validado, e-mail com confirmação, telefone com DDD, foto opcional.',
      confirmation: 'E-mail verificado; credenciais criptografadas e dados mínimos LGPD.',
      errorSolution: 'CPF com dígito inválido ou e-mail duplicado são bloqueados com mensagem descritiva imediata.',
    },
    {
      num: 2,
      title: 'Selecionar Plano e Capacidade',
      objective: 'Escolher a capacidade adequada de membros e cotas simultâneas.',
      screen: 'Contratar Caixinha',
      fields: 'Plano Essencial (20 membros / 40 cotas), Intermediário (50/50) ou Ampliado (Bloqueado). Opção Mensal ou Anual (10x).',
      confirmation: 'Menor faixa que atende simultaneamente membros e cotas é selecionada automaticamente.',
      errorSolution: 'Tentativa de contratar acima de 50 cotas informa que o plano Ampliado está com checkout pendente.',
    },
    {
      num: 3,
      title: 'Aceitar Termos e Pagar Licença',
      objective: 'Assinar eletronicamente o contrato de licença e pagar via Pix da plataforma.',
      screen: 'Checkout de Licença',
      fields: 'Leitura dos termos, hash da versão, valor congelado BRL, QR Code e Copia e Cola Pix.',
      confirmation: 'Reconciliação com conta jurídica da plataforma ativa a licença com status ATIVA.',
      errorSolution: 'Print ou comprovante isolado não ativam o tenant; necessária confirmação autoritativa do provedor.',
    },
    {
      num: 4,
      title: 'Ativar Caixinha (Tenant)',
      objective: 'Transicionar a caixinha de RASCUNHO_INATIVO para ATIVO.',
      screen: 'Minha Caixinha',
      fields: 'Nome de exibição da caixinha, identificador do ciclo financeiro central 2027.',
      confirmation: 'Tenant liberado com isolamento contábil e de permissões.',
      errorSolution: 'Licença não paga ou suspensa impede ativação de novas caixinhas.',
    },
    {
      num: 5,
      title: 'Configurar Políticas e Percentuais',
      objective: 'Fixar regras financeiras (juros, prazo, multas e split admin/membros).',
      screen: 'Políticas da Caixinha',
      fields: 'Taxa periódica mensal, amortização Price, limite de parcelas (até 6 inaugural / 12 outros), percentual admin (ex: 15%) e membros (85%).',
      confirmation: 'Versão de política congelada para todo o ciclo anual.',
      errorSolution: 'Tentativa de alterar o percentual administrativo durante o ano só terá vigência no ciclo subsequente.',
    },
    {
      num: 6,
      title: 'Convidar e Admitir Membros',
      objective: 'Registrar participantes fechados da caixinha.',
      screen: 'Membros e Convites',
      fields: 'Convite nominal, nome completo, CPF, contato e contrato de adesão.',
      confirmation: 'Membro autentica e aceita os termos individualmente antes do acesso financeiro.',
      errorSolution: 'Convite pendente não consome capacidade da licença nem gera direitos.',
    },
    {
      num: 7,
      title: 'Registrar Cotas e Contribuições',
      objective: 'Acompanhar obrigações mensais fixas com vencimento no dia 10 central.',
      screen: 'Contribuições',
      fields: 'Competência (ex: 2027-01), quantidade de cotas, valor devido, status financeiro e temporal.',
      confirmation: 'Pagamento conciliado gera capital confirmado e comprovante rastreável.',
      errorSolution: 'Três meses consecutivos não pagos acionam bloqueio de lucro no encerramento (caixinha inaugural).',
    },
    {
      num: 8,
      title: 'Simular, Analisar e Liberar Crédito',
      objective: 'Operar empréstimos internos sob regime Price com 1º período proporcional.',
      screen: 'Empréstimos',
      fields: 'Principal solicitado, taxa contratada, quantidade de parcelas, 1º vencimento dia 10 do mês seguinte.',
      confirmation: 'Reserva atômica de caixa livre; desembolso Pix gera business_operation_id estável.',
      errorSolution: 'Saldo em caixa insuficiente ou parcela após 31/12 é recusada na simulação.',
    },
    {
      num: 9,
      title: 'Consultar Extratos e Livro-Razão (Ledger)',
      objective: 'Garantir transparência contábil em partidas dobradas e centavos exatos.',
      screen: 'Caixa & Ledger',
      fields: 'Contas contábeis (Caixa, Créditos, Capital, Receitas), Débitos, Créditos e balanço equilibrado.',
      confirmation: 'Σ Débitos = Σ Créditos em todas as transações.',
      errorSolution: 'Não é permitido editar saldo manualmente; correções exigem estorno rastreável.',
    },
    {
      num: 10,
      title: 'Autorização Anual do Administrador-Membro',
      objective: 'Validar consentimento unânime para autoempréstimo do gestor.',
      screen: 'Autorização Anual Própria',
      fields: 'Termo de autorização anual para o ciclo, coleta de assinaturas de todos os demais membros ativos.',
      confirmation: 'Unanimidade 100% ativa permite ao admin solicitar e autoaprovar empréstimo próprio.',
      errorSolution: 'Se um único membro revogar ou novo membro entrar sem anuência, Pix é bloqueado imediatamente.',
    },
    {
      num: 11,
      title: 'Conciliar Pix e Tratar Retornos',
      objective: 'Monitorar pagamentos Pix IN e ordens de desembolso Pix OUT.',
      screen: 'Conciliação Pix',
      fields: 'Idempotência, payload do provedor, estado PENDENTE_CONCILIACAO, CONFIRMADO.',
      confirmation: 'Webhook duplicado é tratado de forma neutra sem duplicar créditos ou saídas.',
      errorSolution: 'Timeout ou resposta ambígua mantém reserva e consulta autoritativamente o provedor antes de retry.',
    },
    {
      num: 12,
      title: 'Gerar Relatórios e Fechamento Anual',
      objective: 'Apurar resultado em 31/12 e liquidar em 10/01 pelo Capital-Dias V2.',
      screen: 'Fechamento Anual',
      fields: 'Receitas líquidas realizadas, despesas, Capital-Dias W_i, divisão de centavos por Maiores Restos.',
      confirmation: 'Centavos residuais alocados rigorosamente aos membros elegíveis; sem sobras para o admin.',
      errorSolution: 'Juros futuros não incorridos não entram na base; resultado não positivo gera rateio zero.',
    },
    {
      num: 13,
      title: 'Renovar Licença e Pro-Rata',
      objective: 'Renovar vigência da licença sem perda de dias e sem prazo de carência.',
      screen: 'Minha Licença',
      fields: 'Adição de 1 ou 12 meses preservando o dia âncora; cálculo proporcional em caso de upgrade.',
      confirmation: 'Licença estendida; dia âncora original preservado mesmo em meses de 28/30 dias.',
      errorSolution: 'Pagamento antecipado soma ao término vigente; pagamento após vencimento inicia nova vigência.',
    },
    {
      num: 14,
      title: 'Suspender e Reativar sem Lesar Membros',
      objective: 'Gerenciar período em caso de atraso na renovação da licença.',
      screen: 'Minha Licença / Status',
      fields: 'Tolerância ZERO DIAS; novas adesões/crédito bloqueados; quitação e extratos preservados.',
      confirmation: 'Pix da licença reativa o sistema automaticamente com auditoria completa.',
      errorSolution: 'Suspensão da licença jamais apaga direitos ou impede o fechamento anual dos membros.',
    },
    {
      num: 15,
      title: 'Solicitar Suporte Excepcional ou Revogar',
      objective: 'Abrir canal técnico seguro para auxílio do Master sem perda de privacidade.',
      screen: 'Suporte Técnico',
      fields: 'Chamado pontual com prazo de até 60 minutos; opção Break-Glass de 30 minutos em emergência.',
      confirmation: 'Master acessa apenas dados operacionais técnicos; sem acesso a extratos individuais ou Pix.',
      errorSolution: 'Admin pode revogar o acesso a qualquer instante, encerrando sessões abertas imediatamente.',
    },
    {
      num: 16,
      title: 'Verificar Trilha de Auditoria e Incidentes',
      objective: 'Auditar todos os atos críticos, decisões, políticas e eventos financeiros.',
      screen: 'Auditoria & Incidentes',
      fields: 'ID, ator, papel, objeto, ação, carimbo de data/hora, motivo e hash de evidência.',
      confirmation: 'Trilha inviolável para prestação de contas aos membros e órgãos reguladores.',
      errorSolution: 'Qualquer tentativa de violação de invariante gera alerta e recusa com registro em auditoria.',
    },
    {
      num: 17,
      title: 'Acessar e Instalar no Mobile (Android & iOS)',
      objective: 'Operar o sistema em smartphones com experiência nativa PWA e segurança biométrica.',
      screen: 'Instalar Aplicativo Mobile',
      fields: 'Suporte a Chrome (Android) e Safari (iOS), ícone de tela inicial, safe-area e modo offline.',
      confirmation: 'Instalação sem loja obrigatória; cache local ultrarrápido e navegação otimizada para toque.',
      errorSolution: 'Problemas de atualização de tela são sanados automaticamente pelo Service Worker em segundo plano.',
    },
    {
      num: 18,
      title: 'Monitorar Arquitetura Multi-Cloud (OCI + GCP)',
      objective: 'Assegurar redundância ativa soberana e custódia imutável do Livro-Razão.',
      screen: 'Arquitetura Multi-Cloud',
      fields: 'Google Cloud Run (São Paulo), Oracle Autonomous DB (Vinhedo), OCI Object Storage WORM e FastConnect.',
      confirmation: 'RPO de 0 segundos e RTO menor que 15 segundos em caso de contingência catastrófica.',
      errorSolution: 'Degradação em um provedor aciona automaticamente a rota do segundo sem perda de transações.',
    },
  ];

  const current = MANUAL_STEPS.find(s => s.num === activeStep) || MANUAL_STEPS[0];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-xs p-4 animate-in fade-in">
      <div className="bg-white rounded-2xl shadow-2xl max-w-4xl w-full max-h-[92vh] flex flex-col overflow-hidden border border-slate-200">
        {/* Header */}
        <div className="bg-slate-900 text-white p-5 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-emerald-500/20 text-emerald-400 flex items-center justify-center">
              <BookOpen className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-bold">Manual Oficial para Administradores de Caixinhas</h2>
                <span className="bg-emerald-500/20 text-emerald-300 text-[10px] font-semibold px-2 py-0.5 rounded-full uppercase tracking-wider">
                  Entregável MVP • Cláusula 11.4
                </span>
              </div>
              <p className="text-slate-400 text-xs">FRcaixinha 2.2 • Guia Prático Passo a Passo (18 Etapas incluindo Mobile & Multi-Cloud)</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Body with Left Step List & Right Step Details */}
        <div className="flex-1 flex overflow-hidden">
          {/* Step Selector List */}
          <div className="w-1/3 border-r border-slate-200 bg-slate-50/80 overflow-y-auto p-3 space-y-1">
            <div className="text-[11px] font-bold text-slate-500 uppercase tracking-wider px-2 py-1.5">
              16 Passos Operacionais
            </div>
            {MANUAL_STEPS.map(step => (
              <button
                key={step.num}
                onClick={() => setActiveStep(step.num)}
                className={`w-full text-left p-2.5 rounded-xl text-xs font-medium transition-all flex items-center justify-between cursor-pointer ${
                  activeStep === step.num
                    ? 'bg-emerald-600 text-white shadow-xs'
                    : 'text-slate-700 hover:bg-slate-200/60'
                }`}
              >
                <div className="flex items-center gap-2.5 truncate">
                  <span
                    className={`w-6 h-6 rounded-full flex items-center justify-center text-[11px] font-bold shrink-0 ${
                      activeStep === step.num ? 'bg-white/20 text-white' : 'bg-slate-200 text-slate-700'
                    }`}
                  >
                    {step.num}
                  </span>
                  <span className="truncate">{step.title}</span>
                </div>
                <ChevronRight className={`w-3.5 h-3.5 shrink-0 ${activeStep === step.num ? 'text-white' : 'text-slate-400'}`} />
              </button>
            ))}
          </div>

          {/* Step Detail View */}
          <div className="flex-1 p-6 overflow-y-auto space-y-5 bg-white">
            <div className="flex items-start justify-between">
              <div>
                <span className="text-xs font-bold text-emerald-700 tracking-wider uppercase">
                  Passo {current.num} de 16
                </span>
                <h3 className="text-xl font-extrabold text-slate-900 mt-0.5">{current.title}</h3>
              </div>
              <div className="flex items-center gap-1.5 text-xs font-medium text-emerald-800 bg-emerald-50 px-2.5 py-1 rounded-lg border border-emerald-200">
                <Shield className="w-3.5 h-3.5 text-emerald-600" />
                <span>Norma Contratual Homologada</span>
              </div>
            </div>

            <div className="grid grid-cols-1 gap-4">
              <div className="p-4 rounded-xl bg-slate-50 border border-slate-200/80 space-y-1">
                <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">Objetivo</span>
                <p className="text-sm text-slate-800 font-medium">{current.objective}</p>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200/80 space-y-1">
                  <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">Tela do Sistema</span>
                  <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-900">
                    <FileText className="w-4 h-4 text-emerald-600" />
                    <span>{current.screen}</span>
                  </div>
                </div>

                <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200/80 space-y-1">
                  <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">Confirmação Esperada</span>
                  <div className="flex items-center gap-1.5 text-xs font-semibold text-emerald-800">
                    <CheckCircle className="w-4 h-4 text-emerald-600" />
                    <span className="truncate">{current.confirmation}</span>
                  </div>
                </div>
              </div>

              <div className="p-4 rounded-xl bg-blue-50/60 border border-blue-100 space-y-1">
                <span className="text-[11px] font-bold text-blue-800 uppercase tracking-wider">Campos Mínimos e Validações</span>
                <p className="text-xs text-blue-950 leading-relaxed">{current.fields}</p>
              </div>

              <div className="p-4 rounded-xl bg-amber-50/70 border border-amber-200 space-y-1">
                <div className="flex items-center gap-1.5 text-amber-900 font-bold text-xs uppercase tracking-wider">
                  <HelpCircle className="w-4 h-4 text-amber-600" />
                  <span>Tratamento de Exceções e Solução de Erro</span>
                </div>
                <p className="text-xs text-amber-950 leading-relaxed">{current.errorSolution}</p>
              </div>
            </div>

            {/* Navigation buttons between steps */}
            <div className="pt-4 border-t border-slate-100 flex items-center justify-between">
              <button
                disabled={activeStep === 1}
                onClick={() => setActiveStep(prev => Math.max(1, prev - 1))}
                className="px-4 py-2 rounded-xl text-xs font-medium border border-slate-200 text-slate-700 hover:bg-slate-100 disabled:opacity-40 cursor-pointer"
              >
                Passo Anterior
              </button>
              <span className="text-xs text-slate-500">
                Página {activeStep} de 16
              </span>
              <button
                disabled={activeStep === 16}
                onClick={() => setActiveStep(prev => Math.min(16, prev + 1))}
                className="px-4 py-2 rounded-xl text-xs font-medium bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-40 cursor-pointer shadow-xs"
              >
                Próximo Passo
              </button>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="bg-slate-100 px-6 py-3 border-t border-slate-200 flex items-center justify-between text-xs text-slate-600">
          <div className="flex items-center gap-2">
            <Award className="w-4 h-4 text-emerald-600" />
            <span>Documento emitido conforme Cláusula 11.4 do Contrato Técnico Mestre</span>
          </div>
          <button
            onClick={onClose}
            className="px-4 py-1.5 bg-slate-900 hover:bg-slate-800 text-white font-medium rounded-lg text-xs cursor-pointer"
          >
            Fechar Manual
          </button>
        </div>
      </div>
    </div>
  );
};
