import React, { useState, useEffect } from 'react';
import {
  Smartphone,
  Share2,
  PlusSquare,
  CheckCircle2,
  Download,
  X,
  Apple,
  ShieldCheck,
  Zap,
  WifiOff,
  Copy,
  QrCode,
  ExternalLink,
  FileArchive,
  RefreshCw,
  Check,
  Wrench,
  AlertTriangle,
  Terminal,
  HelpCircle,
  Laptop
} from 'lucide-react';
import QRCode from 'qrcode';
import { generateProjectZip } from '../services/zipExportService';

interface MobileInstallModalProps {
  isOpen: boolean;
  onClose: () => void;
  onOpenGitHub?: () => void;
}

export const MobileInstallModal: React.FC<MobileInstallModalProps> = ({ isOpen, onClose, onOpenGitHub }) => {
  const [platform, setPlatform] = useState<'TERMUX' | 'QR' | 'TOOLS' | 'ANDROID' | 'IOS'>('TERMUX');
  const [installPromptTriggered, setInstallPromptTriggered] = useState(false);
  const [qrCodeDataUrl, setQrCodeDataUrl] = useState<string>('');
  const [copiedLink, setCopiedLink] = useState(false);
  const [copiedCommand, setCopiedCommand] = useState<string | null>(null);
  const [isZipping, setIsZipping] = useState(false);
  const [zipProgress, setZipProgress] = useState(0);

  // URLs oficiais do applet no Google Cloud Run
  const liveDevUrl = 'https://ais-dev-yod4utszur4g3inwsugmge-471547902048.us-west2.run.app';
  const sharedPreUrl = 'https://ais-pre-yod4utszur4g3inwsugmge-471547902048.us-west2.run.app';

  // Permite o usuário escolher entre o link Dev (ativo agora) e o link público compartilhado
  const [selectedUrlType, setSelectedUrlType] = useState<'DEV' | 'PRE'>('DEV');
  const currentTargetUrl = selectedUrlType === 'DEV' ? liveDevUrl : sharedPreUrl;

  useEffect(() => {
    if (isOpen) {
      QRCode.toDataURL(currentTargetUrl, {
        width: 240,
        margin: 2,
        color: {
          dark: '#022c22',
          light: '#ffffff',
        },
      })
        .then(url => setQrCodeDataUrl(url))
        .catch(err => console.error('Erro ao gerar QR Code:', err));
    }
  }, [isOpen, currentTargetUrl]);

  if (!isOpen) return null;

  const handleCopy = (text: string, identifier: string) => {
    navigator.clipboard.writeText(text).then(() => {
      if (identifier === 'link') {
        setCopiedLink(true);
        setTimeout(() => setCopiedLink(false), 2500);
      } else {
        setCopiedCommand(identifier);
        setTimeout(() => setCopiedCommand(null), 2500);
      }
    });
  };

  const handleTriggerAndroidInstall = () => {
    const deferredPrompt = (window as unknown as { deferredPrompt?: { prompt: () => void; userChoice: Promise<{ outcome: string }> } }).deferredPrompt;
    if (deferredPrompt) {
      deferredPrompt.prompt();
      deferredPrompt.userChoice.then((choiceResult) => {
        if (choiceResult.outcome === 'accepted') {
          setInstallPromptTriggered(true);
        }
      });
    } else {
      setInstallPromptTriggered(true);
    }
  };

  const handleDownloadZipBackup = async () => {
    setIsZipping(true);
    setZipProgress(10);
    try {
      const blob = await generateProjectZip((percent) => {
        setZipProgress(percent);
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'FRcaixinha_2.2_Projeto_Completo_Mobile_MultiCloud.zip';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Erro ao exportar ZIP dinâmico:', err);
      // Fallback para download direto do arquivo servido estaticamente
      window.location.href = '/FRcaixinha_2.2_Projeto_Completo.zip';
    } finally {
      setIsZipping(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in">
      <div className="bg-white rounded-3xl max-w-2xl w-full overflow-hidden shadow-2xl border border-slate-200 flex flex-col max-h-[92vh]">
        {/* Header */}
        <div className="bg-slate-900 text-white p-5 sm:p-6 relative">
          <button
            onClick={onClose}
            className="absolute top-5 right-5 text-slate-400 hover:text-white p-1 rounded-full hover:bg-slate-800 transition-colors cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>

          <div className="flex items-center gap-2 mb-2">
            <span className="text-[10px] font-bold bg-emerald-500 text-slate-950 px-2 py-0.5 rounded-full uppercase tracking-wider">
              Download & Testes no Celular
            </span>
            <span className="text-[10px] font-semibold text-emerald-400">Android & iPhone</span>
          </div>

          <h2 className="text-xl sm:text-2xl font-black tracking-tight text-white flex items-center gap-2">
            <span>Central de Download e Testes Mobile</span>
            <span className="text-emerald-400 font-mono text-xs">v2.2</span>
          </h2>
          <p className="text-xs text-slate-300 mt-1">
            Instale o app no celular, baixe o código-fonte completo em ZIP ou veja as ferramentas para gerar o APK nativo.
          </p>

          {/* Navigation Tabs */}
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-1.5 mt-5 p-1 bg-slate-800 rounded-2xl">
            <button
              onClick={() => setPlatform('TERMUX')}
              className={`flex items-center justify-center gap-1 py-2 px-1 rounded-xl text-[11px] font-bold transition-all cursor-pointer ${
                platform === 'TERMUX' ? 'bg-emerald-600 text-white shadow-sm' : 'text-slate-300 hover:text-white'
              }`}
            >
              <Terminal className="w-3.5 h-3.5 shrink-0 text-emerald-300" />
              <span>Termux Celular</span>
            </button>

            <button
              onClick={() => setPlatform('QR')}
              className={`flex items-center justify-center gap-1 py-2 px-1 rounded-xl text-[11px] font-bold transition-all cursor-pointer ${
                platform === 'QR' ? 'bg-emerald-600 text-white shadow-sm' : 'text-slate-300 hover:text-white'
              }`}
            >
              <QrCode className="w-3.5 h-3.5 shrink-0" />
              <span>QR Code</span>
            </button>

            <button
              onClick={() => setPlatform('ANDROID')}
              className={`flex items-center justify-center gap-1 py-2 px-1 rounded-xl text-[11px] font-bold transition-all cursor-pointer ${
                platform === 'ANDROID' ? 'bg-emerald-600 text-white shadow-sm' : 'text-slate-300 hover:text-white'
              }`}
            >
              <Smartphone className="w-3.5 h-3.5 shrink-0" />
              <span>Android PWA</span>
            </button>

            <button
              onClick={() => setPlatform('TOOLS')}
              className={`flex items-center justify-center gap-1 py-2 px-1 rounded-xl text-[11px] font-bold transition-all cursor-pointer ${
                platform === 'TOOLS' ? 'bg-emerald-600 text-white shadow-sm' : 'text-slate-300 hover:text-white'
              }`}
            >
              <Wrench className="w-3.5 h-3.5 shrink-0 text-amber-300" />
              <span>Ferramentas PC</span>
            </button>

            <button
              onClick={() => setPlatform('IOS')}
              className={`flex items-center justify-center gap-1 py-2 px-1 rounded-xl text-[11px] font-bold transition-all cursor-pointer ${
                platform === 'IOS' ? 'bg-emerald-600 text-white shadow-sm' : 'text-slate-300 hover:text-white'
              }`}
            >
              <Apple className="w-3.5 h-3.5 shrink-0" />
              <span>iPhone</span>
            </button>
          </div>
        </div>

        {/* Modal Body */}
        <div className="p-5 sm:p-6 overflow-y-auto space-y-5 text-xs text-slate-700">
          
          {/* TAB: TERMUX (ANDROID) */}
          {platform === 'TERMUX' && (
            <div className="space-y-4 text-left">
              <div className="p-4 bg-emerald-950 text-white border border-emerald-800 rounded-2xl flex items-start gap-3">
                <Terminal className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" />
                <div className="space-y-1">
                  <div className="font-bold text-white text-xs flex items-center gap-2">
                    <span>SIM! Você pode rodar 100% pelo Termux no Celular</span>
                    <span className="text-[10px] bg-emerald-500 text-slate-950 px-2 py-0.5 rounded-full font-black">Nativo Android</span>
                  </div>
                  <p className="text-[11px] text-emerald-200 leading-relaxed">
                    O Termux é um ambiente Linux completo no Android. Com o Node.js instalado nele, você roda o FR Finance localmente em <code>http://localhost:3000</code> sem precisar de computador!
                  </p>
                </div>
              </div>

              {/* Guia em 4 passos com comandos de 1 toque */}
              <div className="space-y-3">
                {/* Passo 1 */}
                <div className="p-3.5 bg-slate-50 border border-slate-200 rounded-2xl space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-slate-900 text-xs flex items-center gap-2">
                      <span className="w-5 h-5 rounded-full bg-emerald-600 text-white flex items-center justify-center text-[10px] font-bold">1</span>
                      Instalar Node.js, Git e Unzip no Termux
                    </span>
                  </div>
                  <div className="bg-slate-900 p-2.5 rounded-xl font-mono text-[10px] text-emerald-400 flex items-center justify-between gap-2">
                    <span className="truncate">pkg update -y && pkg install -y nodejs git unzip curl</span>
                    <button
                      onClick={() => handleCopy('pkg update -y && pkg install -y nodejs git unzip curl', 'termux-step1')}
                      className="px-2 py-1 bg-slate-800 hover:bg-slate-700 text-white rounded text-[10px] flex items-center gap-1 cursor-pointer shrink-0"
                    >
                      {copiedCommand === 'termux-step1' ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                      <span>{copiedCommand === 'termux-step1' ? 'Copiado' : 'Copiar'}</span>
                    </button>
                  </div>
                </div>

                {/* Passo 2 */}
                <div className="p-3.5 bg-slate-50 border border-slate-200 rounded-2xl space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-slate-900 text-xs flex items-center gap-2">
                      <span className="w-5 h-5 rounded-full bg-emerald-600 text-white flex items-center justify-center text-[10px] font-bold">2</span>
                      Dar Permissão de Armazenamento no Termux
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-500">
                    Isso permite que o Termux acesse a sua pasta <strong>Downloads</strong> do celular:
                  </p>
                  <div className="bg-slate-900 p-2.5 rounded-xl font-mono text-[10px] text-emerald-400 flex items-center justify-between gap-2">
                    <span className="truncate">termux-setup-storage</span>
                    <button
                      onClick={() => handleCopy('termux-setup-storage', 'termux-step2')}
                      className="px-2 py-1 bg-slate-800 hover:bg-slate-700 text-white rounded text-[10px] flex items-center gap-1 cursor-pointer shrink-0"
                    >
                      {copiedCommand === 'termux-step2' ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                      <span>{copiedCommand === 'termux-step2' ? 'Copiado' : 'Copiar'}</span>
                    </button>
                  </div>
                  <p className="text-[10px] text-amber-700 bg-amber-50 p-2 rounded-lg border border-amber-200">
                    * O Android vai abrir uma caixinha na tela perguntando se você permite o acesso. Toque em <strong>"Permitir"</strong>.
                  </p>
                </div>

                {/* Passo 3 */}
                <div className="p-3.5 bg-slate-50 border border-slate-200 rounded-2xl space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-slate-900 text-xs flex items-center gap-2">
                      <span className="w-5 h-5 rounded-full bg-emerald-600 text-white flex items-center justify-center text-[10px] font-bold">3</span>
                      Baixar e Extrair o Pacote no Termux
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-500">
                    Toque no botão abaixo para baixar o pacote pré-compilado pelo Chrome:
                  </p>
                  
                  <div className="flex flex-wrap gap-2 pt-1 pb-1">
                    <a
                      href="/FRcaixinha_2.2_Projeto_Completo.zip"
                      download="FRcaixinha_2.2_Projeto_Completo.zip"
                      className="px-3.5 py-2 bg-emerald-700 hover:bg-emerald-600 text-white font-bold text-xs rounded-xl flex items-center gap-1.5 shadow-sm"
                    >
                      <Download className="w-3.5 h-3.5 text-white" />
                      <span>Projeto Completo ZIP (Para Compilar APK)</span>
                    </a>
                    <a
                      href="/dist.zip"
                      download="dist.zip"
                      className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 font-medium text-xs rounded-xl flex items-center gap-1.5"
                    >
                      <Download className="w-3.5 h-3.5 text-amber-400" />
                      <span>dist.zip (Apenas Web Preview)</span>
                    </a>
                  </div>

                  <p className="text-[10px] text-slate-500">
                    Depois, cole esse comando no Termux para extrair em pasta nova sem sobrescrever:
                  </p>
                  <div className="bg-slate-900 p-2.5 rounded-xl font-mono text-[10px] text-emerald-400 space-y-1 relative">
                    <div>mkdir -p ~/frcaixinha-build && cd ~/frcaixinha-build</div>
                    <div>unzip -q ~/storage/downloads/FRcaixinha_2.2_Projeto_Completo.zip</div>
                    <button
                      onClick={() => handleCopy('mkdir -p ~/frcaixinha-build && cd ~/frcaixinha-build && unzip -q ~/storage/downloads/FRcaixinha_2.2_Projeto_Completo.zip', 'termux-step3')}
                      className="absolute top-2 right-2 px-2 py-1 bg-slate-800 hover:bg-slate-700 text-white rounded text-[10px] flex items-center gap-1 cursor-pointer"
                    >
                      {copiedCommand === 'termux-step3' ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                      <span>{copiedCommand === 'termux-step3' ? 'Copiado' : 'Copiar'}</span>
                    </button>
                  </div>
                </div>

                {/* Passo 4 */}
                <div className="p-3.5 bg-slate-50 border border-slate-200 rounded-2xl space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-slate-900 text-xs flex items-center gap-2">
                      <span className="w-5 h-5 rounded-full bg-emerald-600 text-white flex items-center justify-center text-[10px] font-bold">4</span>
                      Instalar Dependências com npm ci e Iniciar Servidor Local
                    </span>
                  </div>
                  <p className="text-[10px] text-slate-500">
                    O <code>package-lock.json</code> deste projeto foi corrigido e validado com <code>npm ci</code>:
                  </p>
                  <div className="bg-slate-900 p-2.5 rounded-xl font-mono text-[10px] text-emerald-400 space-y-1 relative">
                    <div>npm ci</div>
                    <div>npm run dev</div>
                    <button
                      onClick={() => handleCopy('npm ci\nnpm run dev', 'termux-step4')}
                      className="absolute top-2 right-2 px-2 py-1 bg-slate-800 hover:bg-slate-700 text-white rounded text-[10px] flex items-center gap-1 cursor-pointer"
                    >
                      {copiedCommand === 'termux-step4' ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                      <span>{copiedCommand === 'termux-step4' ? 'Copiado' : 'Copiar'}</span>
                    </button>
                  </div>
                </div>

                {/* Passo 5 */}
                <div className="p-3.5 bg-emerald-50 border border-emerald-200 rounded-2xl space-y-1">
                  <div className="font-bold text-emerald-950 text-xs flex items-center gap-1.5">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                    <span>Como Abrir no Celular</span>
                  </div>
                  <p className="text-[11px] text-emerald-800 leading-relaxed">
                    Assim que o Termux exibir <code>Local: http://localhost:3000/</code>, abra o aplicativo <strong>Google Chrome</strong> no próprio celular e digite:
                  </p>
                  <div className="p-2 bg-white rounded-xl border border-emerald-300 font-mono font-bold text-center text-xs text-emerald-900">
                    http://localhost:3000
                  </div>
                  <p className="text-[10px] text-emerald-700">
                    O aplicativo rodará com ultra-velocidade, offline e com todos os recursos habilitados!
                  </p>
                </div>
              </div>

              {/* Comando Tudo-em-Um para o Termux */}
              <div className="p-3.5 bg-slate-900 text-white rounded-2xl space-y-2">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-bold text-emerald-400 flex items-center gap-1">
                    <Zap className="w-3.5 h-3.5" />
                    <span>Script Rápido (Tudo em 1 Comando):</span>
                  </span>
                  <button
                    onClick={() =>
                      handleCopy(
                        'pkg update -y && pkg install -y nodejs-lts git openjdk-17 unzip curl && termux-setup-storage && mkdir -p ~/frcaixinha-build && cd ~/frcaixinha-build && unzip -q ~/storage/downloads/FRcaixinha_2.2_Projeto_Completo.zip && npm ci && npm run dev',
                        'termux-all'
                      )
                    }
                    className="text-[10px] bg-emerald-600 hover:bg-emerald-500 text-white px-2.5 py-1 rounded-lg flex items-center gap-1 cursor-pointer font-bold"
                  >
                    {copiedCommand === 'termux-all' ? <Check className="w-3 h-3 text-white" /> : <Copy className="w-3 h-3 text-white" />}
                    <span>{copiedCommand === 'termux-all' ? 'Copiado!' : 'Copiar Tudo'}</span>
                  </button>
                </div>
              </div>

              {/* Compilar APK Debug Direto no Termux com Capacitor */}
              <div className="p-4 bg-emerald-900/30 border border-emerald-500/40 rounded-2xl space-y-3">
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-2">
                    <span className="w-5 h-5 rounded-full bg-emerald-600 text-white flex items-center justify-center text-[10px] font-bold">★</span>
                    <span className="font-extrabold text-slate-900 text-xs flex items-center gap-1.5">
                      Compilar APK Debug Nativo no Termux (Capacitor)
                    </span>
                  </div>
                  <span className="text-[10px] font-bold text-emerald-700 bg-emerald-100 px-2 py-0.5 rounded-full">
                    app-debug.apk
                  </span>
                </div>
                <p className="text-[11px] text-slate-600 leading-relaxed">
                  Se você já tem o OpenJDK 17 e o Android SDK no Termux, pode gerar o APK diretamente no celular sem PC. O projeto já inclui a pasta <code className="font-mono text-slate-800 bg-slate-100 px-1 rounded">android/</code> pré-configurada!
                </p>
                <div className="bg-slate-900 p-3 rounded-xl font-mono text-[10px] text-emerald-400 space-y-1 relative">
                  <div className="text-slate-400"># 1. Compilar frontend e sincronizar Capacitor:</div>
                  <div>npm run cap:build</div>
                  <div className="text-slate-400 mt-1"># 2. Gerar APK debug com Gradle Wrapper:</div>
                  <div>cd android && chmod +x gradlew && ./gradlew assembleDebug</div>
                  <div className="text-slate-400 mt-1"># 3. Copiar APK gerado para Downloads:</div>
                  <div>cp app/build/outputs/apk/debug/app-debug.apk ~/storage/downloads/FRcaixinha-2.2-debug.apk</div>
                  <button
                    onClick={() =>
                      handleCopy(
                        'npm run cap:build && cd android && chmod +x gradlew && ./gradlew assembleDebug && cp app/build/outputs/apk/debug/app-debug.apk ~/storage/downloads/FRcaixinha-2.2-debug.apk',
                        'termux-apk-cmd'
                      )
                    }
                    className="absolute top-2 right-2 px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-white rounded-lg text-[10px] flex items-center gap-1 cursor-pointer"
                  >
                    {copiedCommand === 'termux-apk-cmd' ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                    <span>{copiedCommand === 'termux-apk-cmd' ? 'Copiado' : 'Copiar Comandos'}</span>
                  </button>
                </div>
                <div className="text-[10px] text-slate-500 flex items-center justify-between">
                  <span>Guia completo com configuração do <code className="font-mono">local.properties</code>: <strong>docs/BUILD_ANDROID_TERMUX.md</strong></span>
                </div>
              </div>

              {/* Resolução do Erro CANNOT LINK EXECUTABLE node */}
              <div className="p-4 bg-amber-50 border border-amber-300 rounded-2xl space-y-3">
                <div className="flex items-start gap-2.5">
                  <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
                  <div>
                    <span className="font-extrabold text-amber-950 text-xs block">
                      Apareceu o erro "CANNOT LINK EXECUTABLE node"?
                    </span>
                    <span className="text-[10px] text-amber-800 font-mono">
                      cannot locate symbol "_ZNSt6__ndk113__hash_memoryEPKvm"
                    </span>
                  </div>
                </div>

                <p className="text-[11px] text-amber-900 leading-relaxed">
                  Esse erro clássico ocorre quando a biblioteca <strong>libc++</strong> do Termux está desatualizada em relação ao Node.js (muito comum em instalações da Google Play Store). Você tem <strong>duas soluções</strong>:
                </p>

                {/* Solução A: Python */}
                <div className="p-3 bg-white rounded-xl border border-amber-200 space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-xs text-slate-900 flex items-center gap-1.5">
                      <span className="w-4 h-4 rounded-full bg-emerald-600 text-white flex items-center justify-center text-[10px]">A</span>
                      <span>Solução Mais Rápida: Servidor Python (Zero Node.js)</span>
                    </span>
                    <span className="text-[10px] font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full">
                      Recomendado
                    </span>
                  </div>
                  <p className="text-[10px] text-slate-600">
                    O FR Finance já vem pré-compilado na pasta <code className="font-bold text-slate-800">dist/</code>! O Python não tem problemas de compilação C++ no Android e roda com 1 comando:
                  </p>
                  <div className="bg-slate-900 p-2.5 rounded-lg font-mono text-[10px] text-emerald-400 space-y-1 relative">
                    <div>pkg install -y python</div>
                    <div>cd ~/frcaixinha/dist</div>
                    <div>python -m http.server 3000</div>
                    <button
                      onClick={() => handleCopy('pkg install -y python && cd ~/frcaixinha/dist && python -m http.server 3000', 'termux-python')}
                      className="absolute top-2 right-2 px-2 py-1 bg-slate-800 hover:bg-slate-700 text-white rounded text-[10px] flex items-center gap-1 cursor-pointer"
                    >
                      {copiedCommand === 'termux-python' ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                      <span>{copiedCommand === 'termux-python' ? 'Copiado' : 'Copiar'}</span>
                    </button>
                  </div>
                  <p className="text-[10px] text-slate-500">
                    Em seguida, abra <strong>http://localhost:3000</strong> no Chrome do celular!
                  </p>
                </div>

                {/* Solução B: Corrigir o Node no Termux */}
                <div className="p-3 bg-white rounded-xl border border-amber-200 space-y-1.5">
                  <span className="font-bold text-xs text-slate-900 flex items-center gap-1.5">
                    <span className="w-4 h-4 rounded-full bg-indigo-600 text-white flex items-center justify-center text-[10px]">B</span>
                    <span>Corrigir as bibliotecas do Node.js no Termux</span>
                  </span>
                  <p className="text-[10px] text-slate-600">
                    Atualize os pacotes base e a biblioteca C++ do Termux executando:
                  </p>
                  <div className="bg-slate-900 p-2.5 rounded-lg font-mono text-[10px] text-emerald-400 space-y-1 relative">
                    <div>pkg update -y && pkg upgrade -y</div>
                    <div>pkg install -y libc++ nodejs-lts</div>
                    <button
                      onClick={() => handleCopy('pkg update -y && pkg upgrade -y && pkg install -y libc++ nodejs-lts', 'termux-fix-node')}
                      className="absolute top-2 right-2 px-2 py-1 bg-slate-800 hover:bg-slate-700 text-white rounded text-[10px] flex items-center gap-1 cursor-pointer"
                    >
                      {copiedCommand === 'termux-fix-node' ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                      <span>{copiedCommand === 'termux-fix-node' ? 'Copiado' : 'Copiar'}</span>
                    </button>
                  </div>
                  <p className="text-[9px] text-slate-500 italic">
                    * Dica: Se o Termux foi baixado da Google Play Store (abandonada em 2020), o recomendado é instalar a versão oficial moderna via F-Droid (f-droid.org) ou GitHub Releases.
                  </p>
                </div>
              </div>
            </div>
          )}
          
          {/* TAB 1: QR CODE DIRECT SCAN */}
          {platform === 'QR' && (
            <div className="flex flex-col items-center text-center space-y-4">
              
              {/* Alerta explicativo do Erro 404 no ais-pre */}
              <div className="w-full text-left p-3.5 bg-amber-50 border border-amber-200 rounded-2xl flex items-start gap-3">
                <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
                <div className="space-y-1">
                  <div className="font-bold text-amber-950 text-xs">Aviso sobre o Erro 404 (ais-pre vs ais-dev):</div>
                  <p className="text-[11px] text-amber-800 leading-relaxed">
                    O link terminado em <code className="bg-amber-100 px-1 py-0.5 rounded font-mono text-[10px]">ais-pre-...</code> só fica ativo no Google Cloud após você clicar no botão <strong>"Share" (Compartilhar)</strong> no menu superior do Google AI Studio. O link que já está <strong>100% ativo agora</strong> é o <code className="bg-amber-100 px-1 py-0.5 rounded font-mono text-[10px]">ais-dev-...</code>.
                  </p>
                </div>
              </div>

              {/* Seletor de Link */}
              <div className="w-full flex items-center justify-between p-2 bg-slate-100 rounded-2xl">
                <span className="text-[11px] font-bold text-slate-700 ml-2">Qual link escanear?</span>
                <div className="flex items-center gap-1 bg-white p-1 rounded-xl shadow-xs border border-slate-200">
                  <button
                    onClick={() => setSelectedUrlType('DEV')}
                    className={`px-3 py-1 rounded-lg text-[10px] font-bold transition-all cursor-pointer ${
                      selectedUrlType === 'DEV'
                        ? 'bg-emerald-600 text-white shadow-xs'
                        : 'text-slate-600 hover:text-slate-900'
                    }`}
                  >
                    🟢 Link Dev (Ativo Agora)
                  </button>
                  <button
                    onClick={() => setSelectedUrlType('PRE')}
                    className={`px-3 py-1 rounded-lg text-[10px] font-bold transition-all cursor-pointer ${
                      selectedUrlType === 'PRE'
                        ? 'bg-indigo-600 text-white shadow-xs'
                        : 'text-slate-600 hover:text-slate-900'
                    }`}
                  >
                    🌐 Link Share (Público)
                  </button>
                </div>
              </div>

              {/* QR Code Container */}
              <div className="p-3 bg-slate-50 border border-slate-200 rounded-3xl shadow-inner inline-block">
                {qrCodeDataUrl ? (
                  <img
                    src={qrCodeDataUrl}
                    alt="QR Code FR Finance Mobile"
                    className="w-48 h-48 rounded-2xl mx-auto shadow-sm"
                  />
                ) : (
                  <div className="w-48 h-48 flex items-center justify-center text-slate-400">
                    <RefreshCw className="w-8 h-8 animate-spin" />
                  </div>
                )}
              </div>

              <div className="space-y-1 max-w-md">
                <div className="font-extrabold text-sm text-slate-900">
                  Aponte a Câmera do seu Smartphone
                </div>
                <p className="text-[11px] text-slate-500 leading-relaxed">
                  {selectedUrlType === 'DEV' ? (
                    <span>
                      Abre o servidor em tempo real. No celular, certifique-se de estar conectado no Chrome com a sua conta Google (<strong>fr.onassor@gmail.com</strong>).
                    </span>
                  ) : (
                    <span>
                      Link público sem necessidade de login no Google. <em>(Requer que você tenha clicado no botão "Share/Publicar" no cabeçalho do AI Studio).</em>
                    </span>
                  )}
                </p>
              </div>

              {/* Copy URL Bar */}
              <div className="w-full flex items-center gap-2 p-2 bg-slate-50 border border-slate-200 rounded-2xl">
                <input
                  type="text"
                  readOnly
                  value={currentTargetUrl}
                  className="bg-transparent flex-1 text-[11px] font-mono text-slate-600 px-2 outline-none select-all truncate"
                />
                <button
                  onClick={() => handleCopy(currentTargetUrl, 'link')}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold transition-all cursor-pointer ${
                    copiedLink ? 'bg-emerald-600 text-white' : 'bg-slate-900 hover:bg-slate-800 text-white'
                  }`}
                >
                  {copiedLink ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                  <span>{copiedLink ? 'Copiado!' : 'Copiar'}</span>
                </button>
              </div>
            </div>
          )}

          {/* TAB 2: GUIA COMPLETO DE FERRAMENTAS NECESSÁRIAS */}
          {platform === 'TOOLS' && (
            <div className="space-y-5 text-left">
              <div className="p-3.5 bg-blue-50 border border-blue-200 rounded-2xl flex items-start gap-3">
                <HelpCircle className="w-5 h-5 text-blue-700 shrink-0 mt-0.5" />
                <div className="space-y-1">
                  <div className="font-bold text-blue-950 text-xs">Quais ferramentas você precisa instalar?</div>
                  <p className="text-[11px] text-blue-800 leading-relaxed">
                    Depende de como você quer testar o FR Finance. Veja as 3 opções abaixo:
                  </p>
                </div>
              </div>

              {/* OPÇÃO 1: NO CELULAR (ZERO FERRAMENTAS) */}
              <div className="p-4 bg-slate-50 border border-slate-200 rounded-2xl space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-slate-900 text-xs flex items-center gap-2">
                    <span className="w-5 h-5 rounded-full bg-emerald-600 text-white flex items-center justify-center text-[10px]">1</span>
                    Opção 1: Testar no Celular via Navegador (PWA)
                  </span>
                  <span className="text-[10px] font-bold text-emerald-700 bg-emerald-100 px-2 py-0.5 rounded-full">
                    Nenhuma ferramenta no PC
                  </span>
                </div>
                <p className="text-[11px] text-slate-600 leading-relaxed">
                  Não precisa instalar nada no computador. Basta abrir o link no celular (Google Chrome no Android ou Safari no iPhone) e tocar em <strong>"Adicionar à Tela de Início"</strong>. Ele se comporta como um app nativo, com ícone próprio e suporte offline.
                </p>
              </div>

              {/* OPÇÃO 2: NO COMPUTADOR (NODE.JS + GIT) */}
              <div className="p-4 bg-slate-50 border border-slate-200 rounded-2xl space-y-3">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-slate-900 text-xs flex items-center gap-2">
                    <span className="w-5 h-5 rounded-full bg-indigo-600 text-white flex items-center justify-center text-[10px]">2</span>
                    Opção 2: Rodar no Computador (Localhost:3000)
                  </span>
                  <span className="text-[10px] font-bold text-indigo-700 bg-indigo-100 px-2 py-0.5 rounded-full">
                    Desenvolvimento Local
                  </span>
                </div>
                <div className="text-[11px] text-slate-600 space-y-1">
                  <div><strong>Ferramentas a instalar no seu PC:</strong></div>
                  <ul className="list-disc pl-5 space-y-1">
                    <li>
                      <strong>Node.js LTS (v18 ou v20+)</strong>: Baixe em <a href="https://nodejs.org" target="_blank" rel="noreferrer" className="text-indigo-600 underline">nodejs.org</a> (vem com o npm).
                    </li>
                    <li>
                      <strong>Git</strong>: Baixe em <a href="https://git-scm.com" target="_blank" rel="noreferrer" className="text-indigo-600 underline">git-scm.com</a>.
                    </li>
                    <li>
                      <strong>VS Code (opcional)</strong>: Editor recomendado (<a href="https://code.visualstudio.com" target="_blank" rel="noreferrer" className="text-indigo-600 underline">code.visualstudio.com</a>).
                    </li>
                  </ul>
                </div>

                <div className="bg-slate-900 p-2.5 rounded-xl font-mono text-[10px] text-slate-200 space-y-1 relative">
                  <div className="text-slate-400"># Comandos após extrair o arquivo .ZIP:</div>
                  <div>npm install</div>
                  <div>npm run dev</div>
                  <button
                    onClick={() => handleCopy('npm install\nnpm run dev', 'cmd-local')}
                    className="absolute top-2 right-2 text-[10px] bg-slate-800 hover:bg-slate-700 px-2 py-1 rounded text-white flex items-center gap-1 cursor-pointer"
                  >
                    {copiedCommand === 'cmd-local' ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                    <span>{copiedCommand === 'cmd-local' ? 'Copiado' : 'Copiar'}</span>
                  </button>
                </div>
              </div>

              {/* OPÇÃO 3: GERAR O APK NATIVO ANDROID */}
              <div className="p-4 bg-slate-50 border border-slate-200 rounded-2xl space-y-3">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-slate-900 text-xs flex items-center gap-2">
                    <span className="w-5 h-5 rounded-full bg-amber-600 text-white flex items-center justify-center text-[10px]">3</span>
                    Opção 3: Gerar Arquivo APK para Instalar no Celular
                  </span>
                  <span className="text-[10px] font-bold text-amber-700 bg-amber-100 px-2 py-0.5 rounded-full">
                    APK Nativo
                  </span>
                </div>
                <div className="text-[11px] text-slate-600 space-y-1">
                  <div><strong>Ferramentas necessárias no seu PC para compilar APK:</strong></div>
                  <ul className="list-disc pl-5 space-y-1">
                    <li><strong>Node.js (v18+)</strong></li>
                    <li><strong>Java JDK 17</strong> (Azul Zulu ou OpenJDK 17)</li>
                    <li><strong>Android Studio</strong> (com Android SDK Build-Tools e Platform-Tools instalados)</li>
                  </ul>
                </div>

                <div className="bg-slate-900 p-2.5 rounded-xl font-mono text-[10px] text-slate-200 space-y-1 relative">
                  <div className="text-slate-400"># Comandos para gerar o projeto Android com Capacitor:</div>
                  <div>npm install @capacitor/core @capacitor/cli @capacitor/android</div>
                  <div>npx cap init "FR Finance" "com.frcaixinha.app" --web-dir dist</div>
                  <div>npm run build</div>
                  <div>npx cap add android</div>
                  <div>npx cap open android</div>
                  <button
                    onClick={() =>
                      handleCopy(
                        'npm install @capacitor/core @capacitor/cli @capacitor/android\nnpx cap init "FR Finance" "com.frcaixinha.app" --web-dir dist\nnpm run build\nnpx cap add android\nnpx cap open android',
                        'cmd-cap'
                      )
                    }
                    className="absolute top-2 right-2 text-[10px] bg-slate-800 hover:bg-slate-700 px-2 py-1 rounded text-white flex items-center gap-1 cursor-pointer"
                  >
                    {copiedCommand === 'cmd-cap' ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                    <span>{copiedCommand === 'cmd-cap' ? 'Copiado' : 'Copiar'}</span>
                  </button>
                </div>
                <p className="text-[10px] text-slate-500 italic">
                  O Android Studio abrirá o projeto automaticamente. Basta clicar no botão "Build APK" para gerar o arquivo <span className="font-mono font-bold text-slate-700">app-debug.apk</span> e passar para o seu celular!
                </p>

                {/* Nota de Segurança e Bloqueio do APK */}
                <div className="p-3 bg-amber-50/80 border border-amber-300 rounded-xl space-y-1">
                  <div className="flex items-center gap-1.5 text-amber-900 font-bold text-[11px]">
                    <ShieldCheck className="w-3.5 h-3.5 text-amber-700" />
                    <span>Conformidade de Segurança Mobile (Capacitor & Keystore):</span>
                  </div>
                  <p className="text-[10px] text-amber-800 leading-relaxed">
                    Tokens de sessão nunca devem ser armazenados em <code className="font-mono bg-amber-100 px-1 rounded">localStorage</code> ou <code className="font-mono bg-amber-100 px-1 rounded">SharedPreferences</code> no celular. No app nativo Android, deve-se obrigatoriamente instalar o plugin <code className="font-mono bg-amber-100 px-1 rounded">@capacitor-community/secure-storage-plugin</code> para criptografia de hardware via <strong>Android Keystore (AES-256-GCM)</strong> e <strong>iOS Keychain</strong>.
                  </p>
                  <p className="text-[10px] text-slate-600 font-medium pt-1">
                    Status no ambiente AI Studio: <span className="font-bold text-amber-700">BLOQUEADO</span> (exige computador com Android Studio e JDK instalados; não é possível compilar binários nativos .apk diretamente pelo sandbox Web).
                  </p>
                </div>
              </div>

            </div>
          )}

          {/* TAB 3: ANDROID CHROME INSTRUCTIONS */}
          {platform === 'ANDROID' && (
            <div className="space-y-4">
              <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-2xl flex items-start gap-3">
                <Download className="w-5 h-5 text-emerald-700 shrink-0 mt-0.5" />
                <div className="space-y-1">
                  <div className="font-bold text-slate-900">Instalação Direta no Android (Sem Loja)</div>
                  <p className="text-[11px] text-slate-600 leading-relaxed">
                    O FR Finance é um Progressive Web App completo. Ele se integra ao Android com ícone próprio na gaveta de aplicativos, execução em tela cheia e armazenamento local.
                  </p>
                </div>
              </div>

              <div className="space-y-3">
                <div className="flex items-start gap-3 p-3 bg-slate-50 border border-slate-200 rounded-xl">
                  <div className="w-6 h-6 rounded-full bg-emerald-600 text-white font-bold flex items-center justify-center text-xs shrink-0">
                    1
                  </div>
                  <div>
                    <span className="font-bold text-slate-900">Abra o Link no Google Chrome do Celular:</span>
                    <p className="text-[11px] text-slate-500 mt-0.5">
                      Abra <code className="bg-slate-200 px-1 py-0.5 rounded text-[10px] font-mono">{liveDevUrl}</code>. Se pedir login, entre com a sua conta Google (fr.onassor@gmail.com).
                    </p>
                  </div>
                </div>

                <div className="flex items-start gap-3 p-3 bg-slate-50 border border-slate-200 rounded-xl">
                  <div className="w-6 h-6 rounded-full bg-emerald-600 text-white font-bold flex items-center justify-center text-xs shrink-0">
                    2
                  </div>
                  <div>
                    <span className="font-bold text-slate-900">Instalar Aplicativo:</span>
                    <p className="text-[11px] text-slate-500 mt-0.5">
                      O Chrome exibirá um pop-up inferior ou banner <strong>"Adicionar FR Finance à tela inicial"</strong>. Caso não apareça, toque nos 3 pontinhos (<span className="font-mono">⋮</span>) no canto superior direito e selecione <strong>"Instalar aplicativo"</strong>.
                    </p>
                  </div>
                </div>
              </div>

              <button
                onClick={handleTriggerAndroidInstall}
                className="w-full py-3 px-4 bg-emerald-600 hover:bg-emerald-500 text-white rounded-2xl font-bold flex items-center justify-center gap-2 shadow-lg shadow-emerald-600/20 cursor-pointer transition-all"
              >
                <Download className="w-4 h-4" />
                <span>{installPromptTriggered ? 'Aplicativo Instalado ou Pronto no Aparelho' : 'Instalar no Android Agora'}</span>
              </button>
            </div>
          )}

          {/* TAB 4: IPHONE SAFARI INSTRUCTIONS */}
          {platform === 'IOS' && (
            <div className="space-y-4">
              <div className="p-4 bg-blue-50 border border-blue-200 rounded-2xl flex items-start gap-3">
                <Apple className="w-5 h-5 text-blue-700 shrink-0 mt-0.5" />
                <div className="space-y-1">
                  <div className="font-bold text-slate-900">Como Instalar no iPhone (Safari iOS)</div>
                  <p className="text-[11px] text-slate-600 leading-relaxed">
                    A Apple permite adicionar o aplicativo diretamente à tela de início sem precisar da App Store:
                  </p>
                </div>
              </div>

              <div className="space-y-3">
                <div className="flex items-start gap-3 p-3.5 bg-slate-50 border border-slate-200 rounded-2xl">
                  <div className="w-7 h-7 rounded-xl bg-slate-900 text-white flex items-center justify-center shrink-0">
                    <Share2 className="w-4 h-4 text-emerald-400" />
                  </div>
                  <div>
                    <div className="font-bold text-slate-900">Passo 1: Toque em "Compartilhar"</div>
                    <p className="text-[11px] text-slate-500 mt-0.5">
                      No Safari do iPhone, toque no botão central inferior de compartilhamento (ícone com quadrado e seta para cima).
                    </p>
                  </div>
                </div>

                <div className="flex items-start gap-3 p-3.5 bg-slate-50 border border-slate-200 rounded-2xl">
                  <div className="w-7 h-7 rounded-xl bg-slate-900 text-white flex items-center justify-center shrink-0">
                    <PlusSquare className="w-4 h-4 text-emerald-400" />
                  </div>
                  <div>
                    <div className="font-bold text-slate-900">Passo 2: "Adicionar à Tela de Início"</div>
                    <p className="text-[11px] text-slate-500 mt-0.5">
                      Role o menu para baixo e selecione a opção <strong>"Adicionar à Tela de Início"</strong>.
                    </p>
                  </div>
                </div>

                <div className="flex items-start gap-3 p-3.5 bg-slate-50 border border-slate-200 rounded-2xl">
                  <div className="w-7 h-7 rounded-xl bg-slate-900 text-white flex items-center justify-center shrink-0">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  </div>
                  <div>
                    <div className="font-bold text-slate-900">Passo 3: Confirmar</div>
                    <p className="text-[11px] text-slate-500 mt-0.5">
                      Toque em <strong>"Adicionar"</strong> no canto superior direito. O app abrirá em tela cheia com o ícone oficial.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Download Full Project ZIP & GitHub Section */}
          <div className="pt-3 border-t border-slate-200 flex flex-col sm:flex-row items-center justify-between gap-3">
            <div className="space-y-0.5 text-left w-full sm:w-auto">
              <span className="font-bold text-slate-900 block text-xs">Download Direto do Projeto (.ZIP)</span>
              <span className="text-[10px] text-slate-500">Pacote oficial (1.2 MB) com código, contratos e configurações</span>
            </div>

            <div className="flex items-center gap-2 w-full sm:w-auto">
              {/* Botão de Download Direto via Link HTTP */}
              <a
                href="/FRcaixinha_2.2_Projeto_Completo.zip"
                download="FRcaixinha_2.2_Projeto_Completo.zip"
                className="flex-1 sm:flex-none flex items-center justify-center gap-1.5 px-3.5 py-2 bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs rounded-xl shadow-xs transition-all cursor-pointer"
              >
                <Download className="w-3.5 h-3.5" />
                <span>Baixar ZIP (1.2 MB)</span>
              </a>

              {onOpenGitHub && (
                <button
                  onClick={() => {
                    onClose();
                    onOpenGitHub();
                  }}
                  className="flex items-center gap-1.5 px-3 py-2 bg-slate-900 hover:bg-slate-800 text-white font-bold text-xs rounded-xl transition-colors cursor-pointer"
                >
                  <Laptop className="w-3.5 h-3.5 text-indigo-400" />
                  <span>GitHub & Terminal</span>
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 bg-slate-50 border-t border-slate-200 flex items-center justify-between text-xs">
          <span className="text-slate-500 text-[11px]">Compatível com Android 8.0+ e iOS 14.0+</span>
          <button
            onClick={onClose}
            className="px-4 py-2 bg-slate-900 hover:bg-slate-800 text-white rounded-xl font-bold cursor-pointer transition-colors"
          >
            Fechar
          </button>
        </div>
      </div>
    </div>
  );
};
