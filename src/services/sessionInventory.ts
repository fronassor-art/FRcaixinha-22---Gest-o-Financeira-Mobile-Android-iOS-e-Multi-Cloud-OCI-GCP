/** Inventário do PRÓPRIO usuário. Nunca autoriza ou revoga sessão no servidor. */
import type {AuthenticatedUser,UserSessionInfo} from './authService';

const uuid=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const timestamp=/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/;
const obj=(v:unknown):v is Record<string,unknown>=>typeof v==='object'&&v!==null&&!Array.isArray(v);
const parseTime=(v:unknown):number=>{
 if(typeof v!=='string'||!timestamp.test(v))throw Error('Data da sessão inválida.');
 const n=Date.parse(v);
 if(!Number.isFinite(n))throw Error('Data da sessão inválida.');
 return n;
};
const permittedFields = new Set([
 'id','role','tenant_id','created_at','expires_at','current'
]);

export function parseServerSessionInventory(
 raw:unknown,expected:Pick<AuthenticatedUser,'role'|'tenantId'>
):UserSessionInfo[]{
 if(!obj(raw)||raw.source!=='POSTGRESQL_AUTH'||!Array.isArray(raw.sessions)||
    !raw.sessions.length||raw.sessions.length>100)
   throw Error('Inventário de sessões inválido.');
 const seen=new Set<string>();
 let currentCount=0;
 const sessions:UserSessionInfo[]=[];
 for(const row of raw.sessions){
   if(!obj(row)||typeof row.id!=='string'||!uuid.test(row.id)||
     typeof row.role!=='string'||
     !['MASTER','TENANT_ADMIN','TENANT_MEMBER'].includes(row.role)||
     typeof row.current!=='boolean'||
     Object.keys(row).some(field=>!permittedFields.has(field)))
     throw Error('Sessão malformada ou com campos privados.');
   const key=row.id.toLowerCase();
   if(seen.has(key))throw Error('Sessão duplicada.');
   seen.add(key);
   if(row.tenant_id!==null&&
      (typeof row.tenant_id!=='string'||!uuid.test(row.tenant_id)))
      throw Error('Tenant da sessão inválido.');
   const tenant=row.tenant_id as string|null;
   if((row.role==='MASTER'&&tenant!==null)||
      (row.role!=='MASTER'&&tenant===null))
     throw Error('Papel e caixinha incompatíveis.');
   const start=parseTime(row.created_at),end=parseTime(row.expires_at);
   if(start>end)throw Error('Datas da sessão incoerentes.');
   if(row.current){
     currentCount++;
     if(row.role!==expected.role||tenant!==(expected.tenantId??null))
       throw Error('Sessão atual não corresponde ao perfil autenticado.');
   }
   sessions.push({
     id:row.id,role:row.role as UserSessionInfo['role'],
     tenant_id:tenant,created_at:row.created_at as string,
     expires_at:row.expires_at as string,current:row.current,
   });
 }
 if(currentCount!==1)throw Error('Sessão atual ausente ou duplicada.');
 return sessions;
}
