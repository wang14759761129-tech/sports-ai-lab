export const demoDiagnostics:Array<{at:string;type:string;detail:string}>=[];
export function recordDemoDiagnostic(type:string,detail:string){demoDiagnostics.push({at:new Date().toISOString(),type,detail});if(demoDiagnostics.length>200)demoDiagnostics.shift()}
export function createMutationGuard(){let running=false;return {begin(){if(running)return false;running=true;return true},end(){running=false},get pending(){return running}}}
export async function fetchWithTimeout(fetcher:typeof fetch,input:RequestInfo|URL,options:RequestInit={},timeoutMs=8000):Promise<Response>{
 const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),timeoutMs);
 try{const response=await fetcher(input,{...options,signal:controller.signal});recordDemoDiagnostic('request',String(input)+' HTTP '+response.status);return response}catch(error){recordDemoDiagnostic('request-error',String(input)+' '+String(error));if(controller.signal.aborted)throw Error('请求超时，请刷新时刻列表确认后再操作');throw error}finally{clearTimeout(timer)}
}
