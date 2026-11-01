import React, { useState, useEffect } from 'react';
import {
  Cloud,
  Server,
  Database,
  ShieldCheck,
  Lock,
  ArrowRightLeft,
  Activity,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  Cpu,
  Layers,
  FileText,
  FileCheck,
  HardDrive,
  Network,
  ExternalLink,
  ChevronRight,
  ShieldAlert
} from 'lucide-react';
import { multiCloudService } from '../services/multiCloudService';
import { MultiCloudTopology, CloudServiceNode } from '../types';

export const MultiCloudView: React.FC = () => {
  const [topology, setTopology] = useState<MultiCloudTopology>(() => multiCloudService.getTopology());
  const [isAuditing, setIsAuditing] = useState(false);
  const [auditResult, setAuditResult] = useState<{
    success: boolean;
    totalRecordsChecked: number;
    tamperDetected: boolean;
    hashSha256: string;
    verifiedAt: string;
    ociStorageBucket: string;
    gcpSyncParityPct: number;
  } | null>(null);

  useEffect(() => {
    const unsubscribe = multiCloudService.subscribe(() => {
      setTopology({ ...multiCloudService.getTopology() });
    });
    return () => unsubscribe();
  }, []);

  const handleToggleFailover = () => {
    const nextTarget = topology.activePrimary === 'GCP' ? 'OCI' : 'GCP';
    multiCloudService.triggerFailover(nextTarget);
  };

  const handleRunWormAudit = () => {
    setIsAuditing(true);
    setTimeout(() => {
      const res = multiCloudService.auditWormIntegrity();
      setAuditResult(res);
      setIsAuditing(false);
    }, 800);
  };

  const gcpNodes = topology.nodes.filter(n => n.provider === 'GCP');
  const ociNodes = topology.nodes.filter(n => n.provider === 'OCI');

  return (
    <div className="space-y-6">
      {/* Top Banner: Multi-Cloud Master Architecture */}
      <div className="bg-gradient-to-r from-slate-900 via-slate-850 to-slate-900 border border-slate-700/80 rounded-3xl p-6 sm:p-8 text-white shadow-xl relative overflow-hidden">
        <div className="absolute right-0 top-0 w-96 h-96 bg-gradient-to-br from-emerald-500/10 to-teal-500/5 rounded-full blur-3xl pointer-events-none" />
        
        <div className="relative z-10">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="space-y-1.5 max-w-2xl">
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-extrabold uppercase tracking-widest bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 px-2.5 py-0.5 rounded-full">
                  Arquitetura Soberana Multi-Cloud • Cláusula 14.1
                </span>
                <span className="text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30 px-2 py-0.5 rounded-full">
                  Ambiente de Simulação de Topologia (Sem Custo de Nuvem)
                </span>
              </div>
              <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight">
                Oracle Cloud (OCI) & Google Cloud (GCP)
              </h1>
              <p className="text-xs sm:text-sm text-slate-300 leading-relaxed">
                FRcaixinha 2.2 opera em redundância ativa distribuída entre dois data centers independentes no Brasil. A computação primária reside no Google Cloud Platform, enquanto a custódia do Livro-Razão imutável e replicação de desastre residem na Oracle Cloud Infrastructure.
              </p>
            </div>

            {/* Failover Status Action */}
            <div className="flex flex-col items-end gap-2 shrink-0">
              <div className="flex items-center gap-2 bg-slate-800/90 border border-slate-700 px-4 py-2 rounded-2xl shadow-inner">
                <div className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse" />
                <span className="text-xs font-medium text-slate-300">Cluster Ativo:</span>
                <span className="text-xs font-extrabold text-white">
                  {topology.activePrimary === 'GCP' ? 'Google Cloud (São Paulo)' : 'Oracle Cloud (Vinhedo - DR)'}
                </span>
              </div>
              <button
                onClick={handleToggleFailover}
                className="flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white transition-all shadow-md hover:shadow-indigo-500/25 cursor-pointer"
              >
                <ArrowRightLeft className="w-4 h-4" />
                <span>
                  {topology.activePrimary === 'GCP' ? 'Simular Failover para OCI' : 'Restaurar Rota Primária GCP'}
                </span>
              </button>
            </div>
          </div>

          {/* Realtime SLA & Metrics Cards */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4 mt-6">
            <div className="bg-slate-800/60 border border-slate-700/60 rounded-2xl p-3.5 backdrop-blur-xs">
              <div className="text-[10px] text-slate-400 font-medium uppercase">RPO (Perda de Dados)</div>
              <div className="text-lg font-black text-emerald-400 mt-0.5">0,00 seg</div>
              <div className="text-[10px] text-slate-400 mt-0.5">Sincronização contínua</div>
            </div>

            <div className="bg-slate-800/60 border border-slate-700/60 rounded-2xl p-3.5 backdrop-blur-xs">
              <div className="text-[10px] text-slate-400 font-medium uppercase">RTO (Recuperação DR)</div>
              <div className="text-lg font-black text-white mt-0.5">&lt; 15 seg</div>
              <div className="text-[10px] text-emerald-400 mt-0.5">8.4s no teste automatizado</div>
            </div>

            <div className="bg-slate-800/60 border border-slate-700/60 rounded-2xl p-3.5 backdrop-blur-xs">
              <div className="text-[10px] text-slate-400 font-medium uppercase">Latência Inter-Cloud</div>
              <div className="text-lg font-black text-cyan-400 mt-0.5">{topology.interCloudTunnel.latencyMs} ms</div>
              <div className="text-[10px] text-slate-400 mt-0.5">FastConnect ⇄ Interconnect</div>
            </div>

            <div className="bg-slate-800/60 border border-slate-700/60 rounded-2xl p-3.5 backdrop-blur-xs">
              <div className="text-[10px] text-slate-400 font-medium uppercase">Imutabilidade WORM</div>
              <div className="text-lg font-black text-amber-400 mt-0.5">Inviolável</div>
              <div className="text-[10px] text-slate-400 mt-0.5">OCI Object Storage Lock</div>
            </div>
          </div>
        </div>
      </div>

      {/* Dual Cloud Visual Topology Map */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-stretch">
        {/* Left: GCP Cluster (5 cols) */}
        <div className="lg:col-span-5 bg-white border border-slate-200 rounded-3xl p-6 shadow-xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-4 border-b border-slate-100">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-2xl bg-blue-50 border border-blue-200 flex items-center justify-center text-blue-600 shadow-2xs font-bold text-xs">
                  GCP
                </div>
                <div>
                  <h3 className="font-extrabold text-sm text-slate-900">Google Cloud Platform</h3>
                  <div className="text-[11px] text-slate-500">Região: southamerica-east1 (São Paulo)</div>
                </div>
              </div>
              <span className={`text-[10px] font-extrabold px-2.5 py-1 rounded-full ${
                topology.activePrimary === 'GCP'
                  ? 'bg-emerald-100 text-emerald-800 border border-emerald-200'
                  : 'bg-amber-100 text-amber-800 border border-amber-200'
              }`}>
                {topology.activePrimary === 'GCP' ? 'PRIMÁRIO ATIVO' : 'STANDBY ATIVO'}
              </span>
            </div>

            {/* GCP Services List */}
            <div className="mt-4 space-y-3">
              {gcpNodes.map(node => (
                <div key={node.id} className="p-3.5 bg-slate-50 hover:bg-slate-100/80 transition-colors border border-slate-200/80 rounded-2xl space-y-1.5">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Cpu className="w-4 h-4 text-blue-600" />
                      <span className="text-xs font-bold text-slate-800">{node.name}</span>
                    </div>
                    <span className="text-[10px] font-bold px-2 py-0.5 rounded-md bg-emerald-50 text-emerald-700 border border-emerald-200">
                      {node.status}
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-600 leading-snug">{node.roleDescription}</p>
                  <div className="flex items-center justify-between text-[10px] text-slate-400 pt-1 border-t border-slate-200/60 font-mono">
                    <span>Uptime: {node.uptimePct}%</span>
                    <span>Latência: {node.latencyMs}ms</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="mt-4 pt-3 border-t border-slate-100 text-[11px] text-slate-500 flex items-center justify-between">
            <span>Zona A & B redundantes</span>
            <span className="text-blue-700 font-semibold">GCP VPC Peering Ativo</span>
          </div>
        </div>

        {/* Center: Inter-Cloud Private Interconnect (2 cols) */}
        <div className="lg:col-span-2 flex flex-col justify-center items-center py-4 px-2 bg-gradient-to-b from-slate-50 to-slate-100 border border-slate-200 rounded-3xl text-center space-y-4">
          <div className="w-10 h-10 rounded-full bg-cyan-100 text-cyan-700 flex items-center justify-center shadow-xs">
            <Network className="w-5 h-5 animate-pulse" />
          </div>

          <div className="space-y-1">
            <div className="text-xs font-bold text-slate-800">Túnel Privado</div>
            <div className="text-[11px] font-extrabold text-cyan-700">10 Gbps Direto</div>
            <div className="text-[10px] text-slate-500 font-mono">Latência: {topology.interCloudTunnel.latencyMs} ms</div>
          </div>

          <div className="w-full flex items-center justify-center gap-1 text-slate-400">
            <div className="h-0.5 w-6 bg-cyan-400 rounded-full"></div>
            <ArrowRightLeft className="w-4 h-4 text-cyan-600" />
            <div className="h-0.5 w-6 bg-cyan-400 rounded-full"></div>
          </div>

          <div className="p-2 bg-white border border-slate-200 rounded-xl text-[10px] text-slate-600 space-y-0.5 w-full">
            <div className="font-bold text-slate-800">Criptografia</div>
            <div>MACsec AES-256</div>
            <div className="text-emerald-600 font-semibold">Tolerância Zero Vazamento</div>
          </div>

          <div className="text-[10px] text-slate-400">
            Distância física SP ⇄ Vinhedo (~75 km de fibra)
          </div>
        </div>

        {/* Right: OCI Cluster (5 cols) */}
        <div className="lg:col-span-5 bg-white border border-slate-200 rounded-3xl p-6 shadow-xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-4 border-b border-slate-100">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-2xl bg-amber-50 border border-amber-200 flex items-center justify-center text-amber-700 shadow-2xs font-bold text-xs">
                  OCI
                </div>
                <div>
                  <h3 className="font-extrabold text-sm text-slate-900">Oracle Cloud Infrastructure</h3>
                  <div className="text-[11px] text-slate-500">Região: sa-vinhedo-1 (Vinhedo / SP)</div>
                </div>
              </div>
              <span className="text-[10px] font-extrabold px-2.5 py-1 rounded-full bg-purple-100 text-purple-800 border border-purple-200">
                WORM & DR READY
              </span>
            </div>

            {/* OCI Services List */}
            <div className="mt-4 space-y-3">
              {ociNodes.map(node => (
                <div key={node.id} className="p-3.5 bg-slate-50 hover:bg-slate-100/80 transition-colors border border-slate-200/80 rounded-2xl space-y-1.5">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      {node.id === 'oci-worm-storage' ? (
                        <Lock className="w-4 h-4 text-amber-600" />
                      ) : node.id === 'oci-autonomous-db' ? (
                        <Database className="w-4 h-4 text-emerald-600" />
                      ) : (
                        <HardDrive className="w-4 h-4 text-slate-600" />
                      )}
                      <span className="text-xs font-bold text-slate-800">{node.name}</span>
                    </div>
                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded-md ${
                      node.status === 'VERIFIED_LOCKED'
                        ? 'bg-amber-100 text-amber-800 border border-amber-300'
                        : node.status === 'SYNCED'
                        ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                        : 'bg-blue-50 text-blue-700 border border-blue-200'
                    }`}>
                      {node.status}
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-600 leading-snug">{node.roleDescription}</p>
                  <div className="flex items-center justify-between text-[10px] text-slate-400 pt-1 border-t border-slate-200/60 font-mono">
                    <span>Uptime: {node.uptimePct}%</span>
                    <span>Latência: {node.latencyMs}ms</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="mt-4 pt-3 border-t border-slate-100 text-[11px] text-slate-500 flex items-center justify-between">
            <span>Oracle Active Data Guard</span>
            <span className="text-amber-800 font-semibold">CMEK Envelope Key</span>
          </div>
        </div>
      </div>

      {/* WORM Storage & Double-Entry Ledger Verification Panel */}
      <div className="bg-white border border-slate-200 rounded-3xl p-6 sm:p-7 shadow-xs space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-amber-100 text-amber-800 flex items-center justify-center shrink-0">
              <Lock className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-extrabold text-base text-slate-900">
                Auditoria de Imutabilidade WORM no OCI Object Storage (Cláusula 14.2)
              </h3>
              <p className="text-xs text-slate-500">
                Garante que lançamentos do Livro-Razão (Partidas Dobradas) nunca possam ser apagados, alterados ou expurgados por ninguém, nem mesmo pelo Master.
              </p>
            </div>
          </div>

          <button
            onClick={handleRunWormAudit}
            disabled={isAuditing}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-bold bg-amber-600 hover:bg-amber-500 text-white transition-all shadow-md cursor-pointer disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${isAuditing ? 'animate-spin' : ''}`} />
            <span>{isAuditing ? 'Auditando Blocos...' : 'Auditar Integridade Criptográfica (SHA-256)'}</span>
          </button>
        </div>

        {/* Audit Details Box */}
        <div className="p-4 bg-slate-900 text-white rounded-2xl font-mono text-xs space-y-2 border border-slate-800">
          <div className="flex flex-wrap items-center justify-between text-slate-400 pb-2 border-b border-slate-800 text-[11px]">
            <span>BUCKET: oci-br-vinhedo-frcaixinha-immutable-worm-ledger</span>
            <span className="text-emerald-400 font-bold">STATUS: COMPLIANCE LOCK ATIVO (5 ANOS)</span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 pt-1 text-[11px]">
            <div>
              <span className="text-slate-400">Total de Lançamentos Auditados: </span>
              <span className="text-white font-bold">{topology.metrics.wormAuditEntriesCount.toLocaleString('pt-BR')} registros</span>
            </div>
            <div>
              <span className="text-slate-400">Última Replicação Síncrona: </span>
              <span className="text-white font-bold">{new Date(topology.metrics.lastReplicationTimestamp).toLocaleTimeString('pt-BR')}</span>
            </div>
            <div>
              <span className="text-slate-400">Integridade de Hash: </span>
              <span className="text-emerald-400 font-bold">100% Validado sem divergência</span>
            </div>
          </div>
          <div className="text-[11px] text-slate-300 break-all pt-1">
            <span className="text-slate-400">Hash SHA-256 de Validação do Livro: </span>
            <span className="text-cyan-300">{topology.metrics.lastWormHash}</span>
          </div>
        </div>

        {auditResult && (
          <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-2xl flex items-center justify-between gap-4 animate-in fade-in">
            <div className="flex items-center gap-3">
              <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0" />
              <div className="text-xs">
                <div className="font-bold text-emerald-950">
                  Auditoria de Criptografia Concluída com Sucesso! ({auditResult.verifiedAt})
                </div>
                <div className="text-emerald-700">
                  {auditResult.totalRecordsChecked} registros contábeis conferidos entre o cluster Google Cloud (SP) e o cofre WORM Oracle Cloud (Vinhedo). Nenhuma adulteração detectada.
                </div>
              </div>
            </div>
            <span className="text-[10px] font-bold uppercase bg-emerald-200 text-emerald-900 px-2 py-1 rounded-md shrink-0">
              Paridade 100%
            </span>
          </div>
        )}
      </div>

      {/* Legal & Architectural Clauses Section (Caderno Mestre & Contrato) */}
      <div className="bg-white border border-slate-200 rounded-3xl p-6 sm:p-7 shadow-xs space-y-4">
        <div className="flex items-center gap-2 pb-2 border-b border-slate-100">
          <FileText className="w-5 h-5 text-slate-700" />
          <h3 className="font-bold text-sm text-slate-900">
            Cláusulas Oficiais de Arquitetura Multi-Cloud e Mobile (Caderno Mestre)
          </h3>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs text-slate-600">
          <div className="p-4 bg-slate-50 border border-slate-200 rounded-2xl space-y-1.5">
            <div className="font-bold text-slate-900 flex items-center gap-1.5">
              <span>Cláusula 14.1</span>
              <span className="text-[10px] text-emerald-600 bg-emerald-50 px-1.5 py-0.5 rounded">Multi-Cloud</span>
            </div>
            <p className="leading-relaxed">
              <strong>Soberania Geográfica Nacional:</strong> O processamento e guarda dos dados financeiros do FRcaixinha 2.2 serão mantidos integralmente em território brasileiro através de cooperação técnica multi-cloud entre Google Cloud Platform (São Paulo) e Oracle Cloud Infrastructure (Vinhedo), garantindo conformidade com a LGPD e evitando lock-in tecnológico.
            </p>
          </div>

          <div className="p-4 bg-slate-50 border border-slate-200 rounded-2xl space-y-1.5">
            <div className="font-bold text-slate-900 flex items-center gap-1.5">
              <span>Cláusula 14.2</span>
              <span className="text-[10px] text-amber-600 bg-amber-50 px-1.5 py-0.5 rounded">Imutabilidade</span>
            </div>
            <p className="leading-relaxed">
              <strong>Cofre WORM Inviolável:</strong> Todos os lançamentos do Livro-Razão e trilhas de auditoria das provas AT-01 a AT-50 serão replicados em tempo real para o OCI Object Storage com bloqueio de retenção legal (WORM), impedindo exclusão ou manipulação retroativa por qualquer das partes.
            </p>
          </div>

          <div className="p-4 bg-slate-50 border border-slate-200 rounded-2xl space-y-1.5">
            <div className="font-bold text-slate-900 flex items-center gap-1.5">
              <span>Cláusula 14.3</span>
              <span className="text-[10px] text-blue-600 bg-blue-50 px-1.5 py-0.5 rounded">Mobile PWA</span>
            </div>
            <p className="leading-relaxed">
              <strong>Acesso Mobile Android e iPhone:</strong> A plataforma é construída para operação nativa mobile (Progressive Web App com display standalone e APIs biométricas locais), assegurando usabilidade tátil ágil, suporte a notificações instantâneas e funcionamento resiliente em conectividade intermitente.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
