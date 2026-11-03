/** Revalidação da sessão após retomar app móvel/navegador.
 * Não emite credenciais, não guarda token e nunca concede autorização offline.
 */
import type {AuthenticatedUser,AuthSessionSnapshot} from './authService';

export interface ResumeAuthPort {
  captureSession(): AuthSessionSnapshot;
  checkCurrentUser(): Promise<AuthenticatedUser|null>;
  invalidateSessionIfCurrent(snapshot: AuthSessionSnapshot): boolean;
}
export interface ForegroundSessionGuard {
  revalidate(): Promise<void>;
  dispose(): void;
}
export function createForegroundSessionGuard(
  auth: ResumeAuthPort,
  onPending: (pending:boolean)=>void,
): ForegroundSessionGuard {
  let running: Promise<void>|null = null;
  let disposed = false;
  const revalidate = ():Promise<void> => {
    if(disposed)return Promise.resolve();
    if(running)return running;
    const snapshot = auth.captureSession();
    if(!snapshot.token)return Promise.resolve();
    onPending(true);
    const task=(async()=>{
      try{
        // A API responde ou invalida localmente em falha/401; nunca
        // confirmar sessão com dados armazenados no dispositivo.
        await auth.checkCurrentUser();
      }catch{
        // Qualquer erro não tratado também fecha a sessão capturada,
        // sem interferir com novo login iniciado durante a requisição.
        auth.invalidateSessionIfCurrent(snapshot);
      }finally{
        if(!disposed)onPending(false);
      }
    })();
    running=task.finally(()=>{running=null;});
    return running;
  };
  return {revalidate,dispose:()=>{disposed=true;}};
}
