import {getApiBaseUrl} from './authService';

export type ContractModelKind = 'SAAS_LICENSE' | 'MEMBER_ADHESION';
export type ContractModelIntegrityState = 'checking' | 'verified' | 'mismatch' | 'unavailable';

type Manifest = {
  schema: 'FR_FINANCE_CONTRACT_MODEL_MANIFEST_V22';
  version: '2.2';
  state: 'DRAFT_ONLY';
  acceptance_enabled: false;
  kind: ContractModelKind;
  sha256: string;
};

const SHA256 = /^[0-9a-f]{64}$/;

function parseManifest(value: unknown, expectedKind: ContractModelKind): Manifest | null {
  if (typeof value !== 'object' || value === null) return null;
  const raw=value as Record<string,unknown>;
  if(raw.schema!=='FR_FINANCE_CONTRACT_MODEL_MANIFEST_V22'
      ||raw.version!=='2.2'||raw.state!=='DRAFT_ONLY'
      ||raw.acceptance_enabled!==false||raw.kind!==expectedKind
      ||typeof raw.sha256!=='string'||!SHA256.test(raw.sha256))return null;
  return raw as Manifest;
}

async function sha256Text(text:string):Promise<string>{
  if(!globalThis.crypto?.subtle)throw new Error('WEB_CRYPTO_UNAVAILABLE');
  const digest=await globalThis.crypto.subtle.digest('SHA-256',new TextEncoder().encode(text));
  return Array.from(new Uint8Array(digest),byte=>byte.toString(16).padStart(2,'0')).join('');
}

/** Fetch only public integrity metadata; no session, cookies, body or acceptance. */
export async function fetchAndVerifyContractModelV22(
  kind:ContractModelKind,
  text:string,
  fetcher:typeof fetch=fetch,
  digestText:(value:string)=>Promise<string>=sha256Text,
  baseUrl:string=getApiBaseUrl(),
):Promise<ContractModelIntegrityState>{
  try{
    const origin=baseUrl.replace(/\/+$/,'');
    if(!origin||typeof text!=='string'||text.length===0)return 'unavailable';
    const response=await fetcher(
      origin+'/api/v1/public/contract-models/v2.2/'+encodeURIComponent(kind),
      {method:'GET',headers:{Accept:'application/json'},cache:'no-store',
       credentials:'omit',redirect:'error'},
    );
    if(!response.ok)return 'unavailable';
    const manifest=parseManifest(await response.json(),kind);
    if(!manifest)return 'unavailable';
    const actual=await digestText(text);
    return actual===manifest.sha256?'verified':'mismatch';
  }catch{
    return 'unavailable';
  }
}
