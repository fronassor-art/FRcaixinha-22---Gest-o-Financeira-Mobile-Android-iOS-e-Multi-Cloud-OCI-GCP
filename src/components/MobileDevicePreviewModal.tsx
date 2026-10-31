import React, { useState } from 'react';
import {
  Smartphone,
  X,
  RotateCw,
  Wifi,
  Battery,
  Signal,
  Apple,
  ExternalLink,
  ChevronLeft,
  Home,
  Check
} from 'lucide-react';
import { MobilePreviewDevice } from '../types';

interface MobileDevicePreviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  children: React.ReactNode;
}

export const MobileDevicePreviewModal: React.FC<MobileDevicePreviewModalProps> = ({
  isOpen,
  onClose,
  children,
}) => {
  const [device, setDevice] = useState<MobilePreviewDevice>('IPHONE_16');
  const [currentTime, setCurrentTime] = useState('09:41');

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-2 sm:p-4 bg-slate-950/90 backdrop-blur-md animate-in fade-in overflow-y-auto">
      <div className="flex flex-col items-center max-w-full my-auto">
        {/* Device Switcher Bar */}
        <div className="mb-3 flex items-center gap-2 bg-slate-900/90 border border-slate-700 p-1.5 rounded-2xl shadow-xl text-white text-xs">
          <button
            onClick={() => setDevice('IPHONE_16')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl font-bold transition-all cursor-pointer ${
              device === 'IPHONE_16' ? 'bg-emerald-600 text-white shadow-sm' : 'text-slate-300 hover:text-white'
            }`}
          >
            <Apple className="w-3.5 h-3.5" />
            <span>iPhone 16 Pro (iOS)</span>
          </button>

          <button
            onClick={() => setDevice('GALAXY_S24')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl font-bold transition-all cursor-pointer ${
              device === 'GALAXY_S24' ? 'bg-emerald-600 text-white shadow-sm' : 'text-slate-300 hover:text-white'
            }`}
          >
            <Smartphone className="w-3.5 h-3.5" />
            <span>Galaxy S24 (Android)</span>
          </button>

          <div className="h-4 w-px bg-slate-700 mx-1"></div>

          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-white hover:bg-slate-800 rounded-xl transition-colors cursor-pointer"
            title="Fechar Simulador Mobile"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Smartphone Shell Frame */}
        <div
          className={`relative bg-slate-900 rounded-[52px] p-3.5 shadow-2xl border-4 transition-all duration-300 ${
            device === 'IPHONE_16'
              ? 'border-slate-750 shadow-emerald-950/40 w-[385px] sm:w-[400px] h-[820px]'
              : 'border-slate-700 shadow-cyan-950/40 w-[385px] sm:w-[400px] h-[820px]'
          }`}
        >
          {/* Outer edge mute / volume buttons mockup */}
          <div className="absolute -left-[7px] top-28 w-[3px] h-10 bg-slate-700 rounded-l-sm" />
          <div className="absolute -left-[7px] top-42 w-[3px] h-14 bg-slate-700 rounded-l-sm" />
          <div className="absolute -left-[7px] top-58 w-[3px] h-14 bg-slate-700 rounded-l-sm" />
          <div className="absolute -right-[7px] top-36 w-[3px] h-20 bg-slate-700 rounded-r-sm" />

          {/* Screen Container */}
          <div className="w-full h-full bg-slate-100 rounded-[42px] overflow-hidden flex flex-col relative shadow-inner">
            {/* Native Status Bar */}
            <div className="bg-slate-900 text-white px-6 pt-3 pb-2 flex items-center justify-between text-xs font-semibold z-40 select-none shrink-0">
              <span className="font-mono text-[11px]">{currentTime}</span>

              {/* Dynamic Island (iPhone) or Punch Hole (Android) */}
              {device === 'IPHONE_16' ? (
                <div className="w-28 h-6 bg-black rounded-full flex items-center justify-end px-2 space-x-1 shadow-md">
                  <div className="w-2.5 h-2.5 rounded-full bg-slate-800/80 border border-slate-700"></div>
                </div>
              ) : (
                <div className="w-4 h-4 bg-black rounded-full shadow-inner border border-slate-800"></div>
              )}

              <div className="flex items-center gap-1.5 text-slate-300">
                <Signal className="w-3 h-3" />
                <Wifi className="w-3 h-3" />
                <Battery className="w-4 h-4 text-emerald-400" />
              </div>
            </div>

            {/* App Viewport (Scrollable Inside Phone) */}
            <div className="flex-1 overflow-y-auto overflow-x-hidden relative flex flex-col">
              {children}
            </div>

            {/* Bottom Home Indicator Bar */}
            <div className="bg-slate-900/95 py-2 flex justify-center items-center shrink-0 z-40 select-none">
              <div className="w-32 h-1 bg-white/70 rounded-full"></div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
