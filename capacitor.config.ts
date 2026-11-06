import type { CapacitorConfig } from '@capacitor/cli';

/**
 * FR Finance — configuracao Capacitor da frente AI Studio
 * Contrato Técnico Mestre (Cláusulas 11.1 e 16.2)
 *
 * NOTAS DE SEGURANÇA E AMBIENTE:
 * 1. webDir aponta para 'dist' gerado pelo build do Vite.
 * 2. androidScheme configurado como 'https' nativo do Capacitor.
 * 3. cleartext desabilitado por padrão (tráfego seguro HTTPS obrigatório).
 * 4. Nenhuma credencial ou URL privada embutida estaticamente no pacote.
 */
// Variant local de homologação: apenas APK debug e API no próprio celular.
// O CI exige uma URL exata para impedir empacotar hosts remotos sem TLS.
const localAndroidTest = process.env.FRCAIXINHA_ANDROID_LOCAL_TEST === '1';
if (localAndroidTest && process.env.VITE_API_URL !== 'http://127.0.0.1:8000') {
  throw new Error('Build Android local exige VITE_API_URL=http://127.0.0.1:8000.');
}

const config: CapacitorConfig = {
  appId: 'com.frcaixinha.app',
  appName: 'FR Finance',
  webDir: 'dist',
  server: {
    androidScheme: localAndroidTest ? 'http' : 'https',
    cleartext: false,
  },
  plugins: {
    // Edge-to-edge obrigatorio no Android recente; WebViews antigos
    // recebem padding nativo e WebViews modernos usam env(safe-area-inset-*).
    // O modo css injeta --safe-area-inset-* em todas as versões compatíveis.
    SystemBars: {
      insetsHandling: 'css',
      initialViewportFitValueHint: 'cover',
      style: 'DARK',
    },
  },
};

export default config;
