/** M40500 — Android device-only profile protection.
 * No passwords, server tokens, third-party SDKs, camera permission or API writes.
 * Biometry unlocks an EXISTING authenticated FastAPI session, never logs in.
 */
import {Capacitor,registerPlugin} from '@capacitor/core';
import type {AuthenticatedUser} from './authService';

interface AndroidSecurity {
  availability():Promise<{available:boolean;native_android:boolean;server_login_replaced:false}>;
  authenticate(args:{accountKey:string}):Promise<{verified:boolean;server_login_replaced:false}>;
  getBiometricEnabled(args:{accountKey:string}):Promise<{enabled:boolean}>;
  setBiometricEnabled(args:{accountKey:string;enabled:boolean}):Promise<{enabled:boolean}>;
  saveAvatar(args:{accountKey:string;jpegBase64:string}):Promise<{saved:boolean}>;
  getAvatar(args:{accountKey:string}):Promise<{jpegBase64:string}>;
  deleteAvatar(args:{accountKey:string}):Promise<{deleted:boolean}>;
}
const native=registerPlugin<AndroidSecurity>('FRDeviceSecurity');
const UUID=/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i;
const DATA=/^[A-Za-z0-9+/]+={0,2}$/;

/** Account/tenant scope only; not a token nor an authorization. */
export function deviceAccountKey(user:AuthenticatedUser|null):string|null{
  if(!user||!UUID.test(user.id)||
    !user.tenantId||!UUID.test(user.tenantId)||
    (user.role!=='TENANT_ADMIN'&&user.role!=='TENANT_MEMBER'))return null;
  return [user.id.toLowerCase(),user.role,user.tenantId.toLowerCase()].join(':');
}
export function isAndroidSecuritySupported():boolean{
  return Capacitor.isNativePlatform() && Capacitor.getPlatform()==='android';
}
function requireDevice(key:string|null):string{
  if(!isAndroidSecuritySupported()||!key)
    throw new Error('Recurso disponível apenas no aplicativo Android de uma conta autenticada.');
  return key;
}
export async function biometricAvailable():Promise<boolean>{
  if(!isAndroidSecuritySupported())return false;
  const status=await native.availability();
  return status.native_android===true&&status.available===true&&
    status.server_login_replaced===false;
}
export async function biometricEnabled(key:string|null):Promise<boolean>{
  if(!isAndroidSecuritySupported()||!key)return false;
  return (await native.getBiometricEnabled({accountKey:key})).enabled===true;
}
export async function biometricChallenge(key:string|null):Promise<void>{
  const accountKey=requireDevice(key);
  if(!await biometricAvailable())
    throw new Error('Cadastre uma digital ou biometria forte nas configurações do Android.');
  const result=await native.authenticate({accountKey});
  if(result.verified!==true||result.server_login_replaced!==false)
    throw new Error('Verificação biométrica não confirmada.');
}
export async function updateBiometricPreference(
  key:string|null,enabled:boolean,
):Promise<boolean>{
  const accountKey=requireDevice(key);
  const result=await native.setBiometricEnabled({accountKey,enabled});
  if(result.enabled!==enabled)throw new Error('Preferência não confirmada.');
  return result.enabled;
}
export async function readPrivateAvatar(key:string|null):Promise<string|null>{
  if(!isAndroidSecuritySupported()||!key)return null;
  const result=await native.getAvatar({accountKey:key});
  if(!result.jpegBase64)return null;
  if(result.jpegBase64.length>360_000||!DATA.test(result.jpegBase64))
    throw new Error('Foto criptografada inválida.');
  return 'data:image/jpeg;base64,'+result.jpegBase64;
}
export async function removePrivateAvatar(key:string|null):Promise<void>{
  const accountKey=requireDevice(key);
  if((await native.deleteAvatar({accountKey})).deleted!==true)
    throw new Error('Exclusão local não confirmada.');
}
export async function savePrivateAvatar(key:string|null,jpegBase64:string):Promise<void>{
  const accountKey=requireDevice(key);
  if(jpegBase64.length<100||jpegBase64.length>320_000||!DATA.test(jpegBase64))
    throw new Error('Foto processada inválida ou muito grande.');
  if((await native.saveAvatar({accountKey,jpegBase64})).saved!==true)
    throw new Error('Gravação privada não confirmada.');
}
export async function preparePrivateJpeg(file:File):Promise<string>{
  if(file.size<1||file.size>5_000_000||
    !['image/jpeg','image/png','image/webp'].includes(file.type))
    throw new Error('Escolha uma foto JPG, PNG ou WebP de até 5 MB.');
  if(typeof createImageBitmap!=='function'||typeof document==='undefined')
    throw new Error('Este Android não permite processar fotos nesta versão.');
  const bitmap=await createImageBitmap(file);
  try {
    if(bitmap.width<1||bitmap.height<1||bitmap.width>12000||bitmap.height>12000)
      throw new Error('Dimensões da foto inválidas.');
    const ratio=Math.min(1,320/Math.max(bitmap.width,bitmap.height));
    const canvas=document.createElement('canvas');
    canvas.width=Math.max(1,Math.round(bitmap.width*ratio));
    canvas.height=Math.max(1,Math.round(bitmap.height*ratio));
    const ctx=canvas.getContext('2d');
    if(!ctx)throw new Error('Não foi possível processar a foto.');
    ctx.fillStyle='#ffffff';
    ctx.fillRect(0,0,canvas.width,canvas.height);
    ctx.drawImage(bitmap,0,0,canvas.width,canvas.height);
    const result=canvas.toDataURL('image/jpeg',0.78);
    if(!result.startsWith('data:image/jpeg;base64,'))
      throw new Error('Falha ao converter a foto para JPG.');
    const encoded=result.slice('data:image/jpeg;base64,'.length);
    if(encoded.length<100||encoded.length>320_000||!DATA.test(encoded))
      throw new Error('A foto excede o limite seguro após compressão.');
    return encoded;
  } finally {
    bitmap.close();
  }
}
