import type { CapacitorConfig } from '@capacitor/cli';

/**
 * FRcaixinha 2.2 — Configuração do Capacitor para Empacotamento Android
 * Contrato Técnico Mestre (Cláusulas 11.1 e 16.2)
 *
 * NOTAS DE SEGURANÇA E AMBIENTE:
 * 1. webDir aponta para 'dist' gerado pelo build do Vite.
 * 2. androidScheme configurado como 'https' nativo do Capacitor.
 * 3. cleartext desabilitado por padrão (tráfego seguro HTTPS obrigatório).
 * 4. Nenhuma credencial ou URL privada embutida estaticamente no pacote.
 */
const config: CapacitorConfig = {
  appId: 'com.frcaixinha.app',
  appName: 'FRcaixinha 2.2',
  webDir: 'dist',
  server: {
    androidScheme: 'https',
    cleartext: false,
  },
  plugins: {
    // Configurações de plugins nativos
  },
};

export default config;
