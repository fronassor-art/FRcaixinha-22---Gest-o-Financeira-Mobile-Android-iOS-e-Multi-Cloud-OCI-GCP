import {authService,getApiBaseUrl} from './authService';
import {readV23,type Scope,type Transport,type Directory,type Workspace,type FormOptions,type OptionKind} from './productTransactionalBoundaryV23';
const transport:Transport={origin:getApiBaseUrl,captureSession:()=>authService.captureSession(),isCurrent:s=>authService.isSessionSnapshotCurrent(s),getUser:()=>authService.getUser(),invalidateIfCurrent:s=>authService.invalidateSessionIfCurrent(s),send:(url,options)=>fetch(url,options)};
export const productTransactionalApiV23={
 capabilities:(s:Scope)=>readV23(transport,s,{kind:'capabilities'}),
 directory:async(s:Scope,offset:number)=>await readV23(transport,s,{kind:'directory',offset}) as Directory,
 options:async(s:Scope,optionKind:OptionKind,cycleId:string|null,offset:number)=>await readV23(transport,s,{kind:'options',optionKind,cycleId,offset}) as FormOptions,
 workspace:async(s:Scope,cycleId:string,offset:number)=>await readV23(transport,s,{kind:'workspace',cycleId,offset}) as Workspace,
};
