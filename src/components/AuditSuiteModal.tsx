import React, { useState } from 'react';
import { X, CheckCircle2, AlertTriangle, ShieldCheck, Play, Filter, FileSpreadsheet, Check } from 'lucide-react';
import { runAllAuditScenarios, AuditScenarioResult } from '../services/auditRunner';

interface AuditSuiteModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const AuditSuiteModal: React.FC<AuditSuiteModalProps> = ({ isOpen, onClose }) => {
  const [results, setResults] = useState<AuditScenarioResult[]>(() => runAllAuditScenarios());
  const [filterCategory, setFilterCategory] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [copiedId, setCopiedId] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleRunTests = () => {
    const updated = runAllAuditScenarios();
    setResults(updated);
  };

  const categories = [
    { key: 'ALL', label: 'Todos os Testes' },
    { key: 'LICENCIAMENTO', label: 'Licenciamento' },
    { key: 'CREDITO_PRICE', label: 'Crédito & Price' },
    { key: 'RATEIO_CENTAVOS', label: 'Rateio & Centavos' },
    { key: 'CALENDARIO', label: 'Calendário Fixo' },
    { key: 'GOVERNANCA', label: 'Governança & Papéis' },
    { key: 'SEGURANCA_LGPD', label: 'Segurança & LGPD' },
    { key: 'BOLOES', label: 'Bolões Oficiais' },
  ];

  const filtered = results.filter(r => {
    if (filterCategory !== 'ALL' && r.category !== filterCategory) return false;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      return (
        r.id.toLowerCase().includes(q) ||
        r.title.toLowerCase().includes(q) ||
        r.description.toLowerCase().includes(q) ||
        r.clauseRef.toLowerCase().includes(q)
      );
    }
    return true;
  });

  const passCount = results.filter(r => r.status === 'PASS').length;
  const failCount = results.filter(r => r.status === 'FAIL').length;

  const handleCopyEvidence = (r: AuditScenarioResult) => {
    const text = `[AUDITORIA FRCAIXINHA 2.2]\nCenário: ${r.id} - ${r.title}\nCláusulas: ${r.clauseRef}\nResultado Esperado: ${r.expectedOutcome}\nResultado Efetivo: ${r.actualOutcome}\nStatus: ${r.status}\nEvidência: ${r.evidence}`;
    navigator.clipboard.writeText(text);
    setCopiedId(r.id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-xs p-4 animate-in fade-in">
      <div className="bg-white rounded-2xl shadow-2xl max-w-5xl w-full max-h-[92vh] flex flex-col overflow-hidden border border-slate-200">
        {/* Header */}
        <div className="bg-slate-900 text-white p-5 flex items-center justify-between border-b border-slate-800">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-indigo-500/20 text-indigo-400 flex items-center justify-center">
              <ShieldCheck className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-bold">Matriz de Auditoria Contratual (AT-01 a AT-50)</h2>
                <span className="bg-indigo-500/20 text-indigo-300 text-[10px] font-semibold px-2 py-0.5 rounded-full uppercase tracking-wider">
                  Cláusula 16.4 e 16.4-A/C/E
                </span>
              </div>
              <p className="text-slate-400 text-xs">Validação automatizada dos invariantes de regras e integridade</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleRunTests}
              className="px-3.5 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-colors cursor-pointer shadow-xs"
            >
              <Play className="w-3.5 h-3.5 fill-current" />
              <span>Re-executar Testes</span>
            </button>
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors cursor-pointer"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Stats bar */}
        <div className="bg-slate-50 border-b border-slate-200 px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-4 text-xs">
            <div className="flex items-center gap-1.5">
              <span className="text-slate-500">Cenários auditados:</span>
              <strong className="text-slate-900 font-bold">{results.length}</strong>
            </div>
            <div className="flex items-center gap-1.5 text-emerald-700 font-semibold bg-emerald-100/70 px-2 py-0.5 rounded-md">
              <CheckCircle2 className="w-4 h-4 text-emerald-600" />
              <span>{passCount} Aprovados (PASS)</span>
            </div>
            {failCount > 0 && (
              <div className="flex items-center gap-1.5 text-rose-700 font-semibold bg-rose-100/70 px-2 py-0.5 rounded-md">
                <AlertTriangle className="w-4 h-4 text-rose-600" />
                <span>{failCount} Falhas (FAIL)</span>
              </div>
            )}
          </div>

          {/* Search */}
          <div className="w-72">
            <input
              type="text"
              placeholder="Buscar por ID, cláusula ou palavra..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              className="w-full text-xs px-3 py-1.5 bg-white border border-slate-300 rounded-lg focus:outline-hidden focus:border-indigo-500"
            />
          </div>
        </div>

        {/* Filter Categories Pill */}
        <div className="px-6 py-2 bg-white border-b border-slate-100 flex items-center gap-1.5 overflow-x-auto text-xs">
          <Filter className="w-3.5 h-3.5 text-slate-400 shrink-0 mr-1" />
          {categories.map(cat => (
            <button
              key={cat.key}
              onClick={() => setFilterCategory(cat.key)}
              className={`px-2.5 py-1 rounded-lg font-medium whitespace-nowrap transition-colors cursor-pointer ${
                filterCategory === cat.key
                  ? 'bg-slate-900 text-white'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              {cat.label}
            </button>
          ))}
        </div>

        {/* Test List */}
        <div className="flex-1 overflow-y-auto p-6 space-y-3 bg-slate-50/50">
          {filtered.length === 0 ? (
            <div className="text-center py-12 text-slate-400 text-sm">
              Nenhum cenário encontrado para este filtro.
            </div>
          ) : (
            filtered.map(r => (
              <div
                key={r.id}
                className="bg-white border border-slate-200 rounded-xl p-4 shadow-2xs hover:border-slate-300 transition-all space-y-2.5"
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-2.5">
                    <span className="font-mono text-xs font-bold bg-slate-100 text-slate-800 px-2 py-0.5 rounded border border-slate-200">
                      {r.id}
                    </span>
                    <h4 className="font-bold text-sm text-slate-900">{r.title}</h4>
                    <span className="text-[11px] font-medium text-slate-500 bg-slate-100 px-2 py-0.5 rounded-full">
                      Cláusula(s): {r.clauseRef}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span
                      className={`text-xs font-bold px-2.5 py-0.5 rounded-full flex items-center gap-1 ${
                        r.status === 'PASS'
                          ? 'bg-emerald-100 text-emerald-800'
                          : 'bg-rose-100 text-rose-800'
                      }`}
                    >
                      {r.status === 'PASS' ? <CheckCircle2 className="w-3.5 h-3.5" /> : <AlertTriangle className="w-3.5 h-3.5" />}
                      {r.status}
                    </span>
                    <button
                      onClick={() => handleCopyEvidence(r)}
                      title="Copiar relatório deste teste"
                      className="p-1 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded transition-colors cursor-pointer"
                    >
                      {copiedId === r.id ? <Check className="w-4 h-4 text-emerald-600" /> : <FileSpreadsheet className="w-4 h-4" />}
                    </button>
                  </div>
                </div>

                <p className="text-xs text-slate-600">{r.description}</p>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs pt-1">
                  <div className="p-2.5 rounded-lg bg-emerald-50/60 border border-emerald-100 text-emerald-950">
                    <span className="font-semibold block text-[10px] text-emerald-700 uppercase tracking-wider mb-0.5">
                      Aceite Contratual Esperado
                    </span>
                    <span>{r.expectedOutcome}</span>
                  </div>
                  <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-200 text-slate-800">
                    <span className="font-semibold block text-[10px] text-slate-500 uppercase tracking-wider mb-0.5">
                      Resultado do Teste no Sistema
                    </span>
                    <span className="font-mono text-[11px]">{r.actualOutcome}</span>
                  </div>
                </div>

                <div className="text-[11px] text-slate-400 pt-1 flex items-center gap-1">
                  <span>Evidência técnica:</span>
                  <span className="text-slate-600 italic">{r.evidence}</span>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Footer */}
        <div className="bg-slate-100 px-6 py-3 border-t border-slate-200 flex items-center justify-between text-xs text-slate-600">
          <span>Relatório oficial para homologação técnica e auditoria de conformidade (Gate G4/G6).</span>
          <button
            onClick={onClose}
            className="px-4 py-1.5 bg-slate-900 hover:bg-slate-800 text-white font-medium rounded-lg text-xs cursor-pointer"
          >
            Fechar Auditoria
          </button>
        </div>
      </div>
    </div>
  );
};
