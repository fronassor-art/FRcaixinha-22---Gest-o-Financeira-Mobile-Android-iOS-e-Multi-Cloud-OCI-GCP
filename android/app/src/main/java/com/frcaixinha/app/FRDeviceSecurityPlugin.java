package com.frcaixinha.app;

import android.Manifest;
import android.content.Context;
import android.content.SharedPreferences;
import android.hardware.biometrics.BiometricManager;
import android.hardware.biometrics.BiometricPrompt;
import android.hardware.fingerprint.FingerprintManager;
import android.os.Build;
import android.os.CancellationSignal;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;

import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.security.KeyStore;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.Locale;
import java.util.concurrent.Executor;

import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

/**
 * M40500: local biometric challenge and AES-GCM encrypted avatars.
 * A fingerprint/face NEVER creates a server session or replays a password.
 * The existing FastAPI login and JWT/session revocation remain authoritative.
 */
@CapacitorPlugin(name = "FRDeviceSecurity")
public final class FRDeviceSecurityPlugin extends Plugin {
    private static final String AVATAR_KEY_ALIAS = "FR_FINANCE_DEVICE_AVATAR_AES_V1";
    private static final int MAX_JPEG_BYTES = 240_000;
    private static final int IV_BYTES = 12;
    private static final String ACCOUNT_PATTERN =
        "(?i)^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}:" +
        "(TENANT_ADMIN|TENANT_MEMBER):" +
        "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$";
    private long lastBiometricAt = 0L;
    private String lastBiometricAccount = null;

    private String accountKey(PluginCall call) {
        String raw = call.getString("accountKey");
        if (raw == null || !raw.matches(ACCOUNT_PATTERN)) {
            throw new IllegalArgumentException("Identidade de perfil local inválida.");
        }
        return raw.toLowerCase(Locale.ROOT);
    }

    private String digest(String input) throws Exception {
        byte[] bytes = MessageDigest.getInstance("SHA-256")
                .digest(input.getBytes(StandardCharsets.UTF_8));
        StringBuilder b = new StringBuilder();
        for (byte item : bytes) b.append(String.format(Locale.ROOT, "%02x", item & 0xff));
        return b.toString();
    }

    private SharedPreferences prefs() {
        return getContext().getSharedPreferences(
                "fr_finance_biometric_preferences_v1", Context.MODE_PRIVATE);
    }

    private boolean isBiometryAvailable() {
        if (Build.VERSION.SDK_INT < 28) return false;
        if (Build.VERSION.SDK_INT >= 30) {
            BiometricManager mgr = getContext().getSystemService(BiometricManager.class);
            return mgr != null && mgr.canAuthenticate(
                BiometricManager.Authenticators.BIOMETRIC_STRONG
            ) == BiometricManager.BIOMETRIC_SUCCESS;
        }
        if (Build.VERSION.SDK_INT == 29) {
            BiometricManager mgr = getContext().getSystemService(BiometricManager.class);
            return mgr != null &&
                    mgr.canAuthenticate() == BiometricManager.BIOMETRIC_SUCCESS;
        }
        FingerprintManager fingerprint = (FingerprintManager)
                getContext().getSystemService(Context.FINGERPRINT_SERVICE);
        return fingerprint != null && fingerprint.isHardwareDetected()
                && fingerprint.hasEnrolledFingerprints();
    }

    @PluginMethod
    public void availability(PluginCall call) {
        JSObject result = new JSObject();
        result.put("available", isBiometryAvailable());
        result.put("native_android", true);
        result.put("server_login_replaced", false);
        call.resolve(result);
    }

    @PluginMethod
    public void authenticate(PluginCall call) {
        final String key;
        try {
            key = accountKey(call);
        } catch (Exception err) {
            call.reject("Identidade inválida.", err);
            return;
        }
        if (!isBiometryAvailable()) {
            call.reject("Biometria forte não disponível ou não cadastrada neste Android.");
            return;
        }
        getActivity().runOnUiThread(() -> {
            try {
                Executor executor = getActivity().getMainExecutor();
                final CancellationSignal cancellation = new CancellationSignal();
                BiometricPrompt prompt = new BiometricPrompt.Builder(getActivity())
                    .setTitle("FR Finance")
                    .setSubtitle("Confirme sua identidade para proteger esta sessão.")
                    .setNegativeButton("Cancelar", executor, (dialog, which) ->
                        call.reject("Verificação biométrica cancelada."))
                    .build();
                prompt.authenticate(cancellation, executor,
                    new BiometricPrompt.AuthenticationCallback() {
                        @Override
                        public void onAuthenticationSucceeded(
                            BiometricPrompt.AuthenticationResult result) {
                            lastBiometricAt = android.os.SystemClock.elapsedRealtime();
                            lastBiometricAccount = key;
                            JSObject out = new JSObject();
                            out.put("verified", true);
                            out.put("server_login_replaced", false);
                            call.resolve(out);
                        }
                        @Override
                        public void onAuthenticationError(int code, CharSequence message) {
                            call.reject("Biometria recusada ou indisponível.");
                        }
                    });
            } catch (Exception err) {
                call.reject("Não foi possível iniciar a biometria Android.", err);
            }
        });
    }

    @PluginMethod
    public void getBiometricEnabled(PluginCall call) {
        try {
            String key = accountKey(call);
            boolean enabled = prefs().getBoolean("bio_" + digest(key), false);
            JSObject out = new JSObject();
            out.put("enabled", enabled);
            call.resolve(out);
        } catch (Exception err) {
            call.reject("Preferência biométrica indisponível.", err);
        }
    }

    @PluginMethod
    public void setBiometricEnabled(PluginCall call) {
        try {
            String key = accountKey(call);
            Boolean value = call.getBoolean("enabled");
            if (value == null) throw new IllegalArgumentException("Preferência ausente.");
            // M40954: require a fresh same-account challenge for either
            // direction; disabling cannot bypass the security preference gate.
            if (!key.equals(lastBiometricAccount) ||
                    android.os.SystemClock.elapsedRealtime() - lastBiometricAt > 45_000L) {
                call.reject("Confirme a biometria antes de alterar a proteção.");
                return;
            }
            prefs().edit().putBoolean("bio_" + digest(key), value).apply();
            lastBiometricAccount = null;
            lastBiometricAt = 0L;
            JSObject out = new JSObject();
            out.put("enabled", value);
            call.resolve(out);
        } catch (Exception err) {
            call.reject("Não foi possível atualizar sua preferência.", err);
        }
    }

    private SecretKey privateAvatarKey() throws Exception {
        KeyStore store = KeyStore.getInstance("AndroidKeyStore");
        store.load(null);
        if (!store.containsAlias(AVATAR_KEY_ALIAS)) {
            KeyGenerator generator = KeyGenerator.getInstance(
                KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore");
            generator.init(new KeyGenParameterSpec.Builder(AVATAR_KEY_ALIAS,
                KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setKeySize(256).build());
            generator.generateKey();
        }
        return ((KeyStore.SecretKeyEntry) store.getEntry(AVATAR_KEY_ALIAS, null))
                .getSecretKey();
    }

    private File avatarFile(String account) throws Exception {
        File folder = new File(getContext().getFilesDir(), "fr_finance_avatars_v1");
        if (!folder.exists() && !folder.mkdirs()) {
            throw new IllegalStateException("Armazenamento privado indisponível.");
        }
        return new File(folder, digest("fr-finance-avatar:" + account) + ".bin");
    }

    private static void assertJpeg(byte[] raw) {
        if (raw == null || raw.length < 10 || raw.length > MAX_JPEG_BYTES ||
                (raw[0] & 0xff) != 0xff || (raw[1] & 0xff) != 0xd8 ||
                (raw[raw.length-2] & 0xff) != 0xff ||
                (raw[raw.length-1] & 0xff) != 0xd9) {
            throw new IllegalArgumentException("Foto JPEG fora do limite privado.");
        }
    }

    @PluginMethod
    public void saveAvatar(PluginCall call) {
        try {
            String account = accountKey(call);
            String encoded = call.getString("jpegBase64");
            if (encoded == null || encoded.length() > 360_000)
                throw new IllegalArgumentException("Foto muito grande.");
            byte[] image = Base64.decode(encoded, Base64.NO_WRAP);
            assertJpeg(image);
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(Cipher.ENCRYPT_MODE, privateAvatarKey());
            byte[] iv = cipher.getIV();
            if (iv.length != IV_BYTES) throw new IllegalStateException("IV inválido.");
            ByteArrayOutputStream buffer = new ByteArrayOutputStream();
            buffer.write(iv);
            buffer.write(cipher.doFinal(image));
            File dest = avatarFile(account);
            File temp = new File(dest.getParentFile(), dest.getName() + ".tmp");
            try (FileOutputStream out = new FileOutputStream(temp, false)) {
                out.write(buffer.toByteArray());
                out.getFD().sync();
            }
            if (!temp.renameTo(dest)) {
                if (dest.exists() && !dest.delete()) throw new IllegalStateException("Falha na troca.");
                if (!temp.renameTo(dest)) throw new IllegalStateException("Falha ao gravar foto.");
            }
            JSObject response = new JSObject();
            response.put("saved", true);
            call.resolve(response);
        } catch (Exception err) {
            call.reject("Não foi possível salvar a foto privada.", err);
        }
    }

    @PluginMethod
    public void getAvatar(PluginCall call) {
        try {
            File file = avatarFile(accountKey(call));
            JSObject response = new JSObject();
            if (!file.isFile()) {
                response.put("jpegBase64", "");
                call.resolve(response);
                return;
            }
            if (file.length() < IV_BYTES + 17 || file.length() > MAX_JPEG_BYTES + 64)
                throw new IllegalStateException("Arquivo de foto inválido.");
            ByteArrayOutputStream readBuffer = new ByteArrayOutputStream();
            try (java.io.FileInputStream in = new java.io.FileInputStream(file)) {
                byte[] block = new byte[4096];
                int count;
                while ((count = in.read(block)) != -1) {
                    readBuffer.write(block, 0, count);
                    if (readBuffer.size() > MAX_JPEG_BYTES + 64)
                        throw new IllegalStateException("Foto criptografada muito grande.");
                }
            }
            byte[] encrypted = readBuffer.toByteArray();
            if (encrypted.length < IV_BYTES + 17 || encrypted.length > MAX_JPEG_BYTES + 64)
                throw new IllegalStateException("Arquivo de foto inválido.");
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(Cipher.DECRYPT_MODE, privateAvatarKey(),
                new GCMParameterSpec(128, Arrays.copyOfRange(encrypted, 0, IV_BYTES)));
            byte[] image = cipher.doFinal(
                encrypted, IV_BYTES, encrypted.length-IV_BYTES);
            assertJpeg(image);
            response.put("jpegBase64", Base64.encodeToString(image, Base64.NO_WRAP));
            call.resolve(response);
        } catch (Exception err) {
            call.reject("Foto privada indisponível ou inválida.", err);
        }
    }

    @PluginMethod
    public void deleteAvatar(PluginCall call) {
        try {
            File file = avatarFile(accountKey(call));
            if (file.exists() && !file.delete())
                throw new IllegalStateException("Não foi possível excluir a foto.");
            JSObject result = new JSObject();
            result.put("deleted", true);
            call.resolve(result);
        } catch (Exception err) {
            call.reject("Não foi possível excluir a foto privada.", err);
        }
    }
}
