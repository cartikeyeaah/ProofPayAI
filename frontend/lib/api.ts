export type Transaction = { id:string; paypal_transaction_id:string; amount:string; currency:string; status:string; transaction_date:string; evidence_count:number };
export type Finding = {id:string;issue_type:string;severity:'low'|'medium'|'high';explanation:string;source_ids:string[];recommendation:string};
export type Analysis = {analysis_id:string;transaction_id:string;status:'queued'|'processing'|'completed'|'failed';findings:Finding[];draft_response:string|null;merchant_approval_required:boolean};
export type Fact = {id:string;name:string;value:string;source:{document_id:string;page:number;start:number;end:number;quote:string}};
export type Evidence = {id:string;filename:string;document_type:string;media_type:string;size_bytes:number;upload_status:string;processing_status:string;analysis_id:string|null;issue_codes:string[];facts:Fact[]};
export type Draft = {analysis_id:string;text:string;version:number;status:'draft'|'approved';warnings:string[];approved_by:string|null;approved_at:string|null};
export type Account = {email:string;merchant_name:string;mode:'demo'|'persistent';csrf_token:string};
export type Activity = {id:string;action:string;resource_id:string;created_at:string;actor:string};
export type Overview = {total_transactions:number;analyzed_transactions:number;open_cases:number;awaiting_review:number;evidence_issues:number;analyses:Analysis[];activity:Activity[];mode:string};
export type Page = {items:Transaction[];total:number;page:number;page_size:number;origins:Record<string,string>};
export type Integration = {mode:string;persistence:string;ocr:string;paypal:string;paypal_verified:boolean;analysis_engine:string;limitations:string[]};
export type Audit = {events:Activity[];revisions:Draft[]};
export type Details = {analysis_id:string;engine:string;failure_code:string|null;result:null|{finding_sources:Record<string,Fact['source'][]>;issues:{code:string;document_id:string|null;message:string}[]}};
const base = (process.env.NEXT_PUBLIC_API_BASE_URL || '/api/v1').replace(/\/$/,'');
let csrf = '';
export const setCsrf = (value:string) => {csrf=value};
const messages:Record<string,string>={AUTH_REQUIRED:'Sign in to continue.',INVALID_LOGIN:'Email or password is incorrect.',CSRF_FAILED:'Your session changed. Reload and sign in again.',VERSION_CONFLICT:'This draft changed. Reload it before saving.',REVIEW_REQUIRED:'Review and acknowledge the warnings before approving.',ANALYSIS_ACTIVE:'An analysis is already running. Refresh its status.',RATE_LIMITED:'Too many requests. Please wait before retrying.',INVALID_FILE_SIZE:'Use a nonempty file no larger than 10 MiB.',INVALID_FILE_SIGNATURE:'The file content does not match its declared type.',UNSUPPORTED_FILE_TYPE:'Choose a supported PDF, PNG, JPEG, or UTF-8 text file.',PAYPAL_NOT_CONFIGURED:'Sandbox credentials and a merchant binding must be configured on the backend.',PAYPAL_SCOPE_MISSING:'The Sandbox app needs Transaction Search permission.',PAYPAL_PERMISSION_DENIED:'Sandbox access is not authorized. Check the app permissions.',DRAFT_NOT_FOUND:'No source-backed draft is available for this analysis.',TRANSACTION_NOT_FOUND:'This transaction is unavailable.',DOCUMENT_LIMIT:'This transaction has reached its 25-document limit.'};
export class ApiError extends Error { constructor(public status:number,public code:string){super(messages[code] || `Request could not be completed (HTTP ${status}).`)} }
export function parseError(status:number,payload:unknown){const code=typeof payload==='object'&&payload!==null&&'error' in payload ? (payload as {error?:{code?:unknown}}).error?.code:undefined;return new ApiError(status,typeof code==='string'?code:'REQUEST_FAILED')}
export async function request<T>(path:string,options:RequestInit={}):Promise<T>{
  try{
    const response=await fetch(base+path,{...options,credentials:'include',cache:'no-store',signal:AbortSignal.timeout(20000),headers:{...(options.body?{'Content-Type':'application/json'}:{}),...(csrf?{'X-CSRF-Token':csrf}:{}),...options.headers}});
    const body=await response.json().catch(()=>null);
    if(!response.ok)throw parseError(response.status,body);
    if(body===null)throw new Error('The backend returned an unexpected response.');
    return body as T;
  }catch(error){if(error instanceof ApiError)throw error;if(error instanceof Error && (error.name==='TimeoutError'||error.name==='AbortError'))throw new Error('The request timed out. Refresh status before retrying.');throw new Error('Cannot reach the backend. Check the connection and retry.')}
}
export const api={
  me:()=>request<Account>('/auth/me'), login:(email:string,password:string)=>request<Account>('/auth/login',{method:'POST',body:JSON.stringify({email,password})}),logout:()=>request('/auth/logout',{method:'POST'}),
  overview:()=>request<Overview>('/overview'), integrations:()=>request<Integration>('/integrations'),
  transactions:(query:string)=>request<Page>('/transaction-page?'+query), transaction:(id:string)=>request<Transaction>('/transactions/'+encodeURIComponent(id)),
  documents:(id:string)=>request<Evidence[]>('/transactions/'+encodeURIComponent(id)+'/documents'), history:(id:string)=>request<Analysis[]>('/transactions/'+encodeURIComponent(id)+'/analyses'),
  analyze:(id:string,key:string)=>request<Analysis>('/transactions/'+encodeURIComponent(id)+'/analyze',{method:'POST',headers:{'Idempotency-Key':key},body:'{}'}),
  analysis:(id:string)=>request<Analysis>('/analysis/'+encodeURIComponent(id)),details:(id:string)=>request<Details>('/analysis/'+encodeURIComponent(id)+'/details'),draft:(id:string)=>request<Draft>('/analysis/'+encodeURIComponent(id)+'/draft'),
  saveDraft:(draft:Draft,text:string)=>request<Draft>('/analysis/'+draft.analysis_id+'/draft',{method:'PUT',body:JSON.stringify({text,version:draft.version})}),
  approve:(draft:Draft)=>request<Draft>('/analysis/'+draft.analysis_id+'/draft/approve',{method:'POST',body:JSON.stringify({version:draft.version,acknowledge_warnings:true})}),
  audit:(id:string)=>request<Audit>('/analysis/'+id+'/audit'),sync:()=>request<{imported:number;skipped:number}>('/integrations/paypal/sync',{method:'POST'})
};
export function upload(id:string,file:File,type:string,progress:(percent:number)=>void):Promise<Evidence>{
 return new Promise((resolve,reject)=>{const xhr=new XMLHttpRequest();xhr.open('POST',base+'/transactions/'+encodeURIComponent(id)+'/documents');xhr.withCredentials=true;xhr.timeout=30000;if(csrf)xhr.setRequestHeader('X-CSRF-Token',csrf);xhr.upload.onprogress=(e)=>{if(e.lengthComputable)progress(Math.round(e.loaded/e.total*100))};xhr.onerror=()=>reject(new Error('Upload connection failed.'));xhr.ontimeout=()=>reject(new Error('Upload timed out. Refresh evidence before retrying.'));xhr.onload=()=>{let body;try{body=JSON.parse(xhr.responseText)}catch{reject(new Error('Unexpected upload response.'));return}if(xhr.status!==201)reject(parseError(xhr.status,body));else resolve(body)};const form=new FormData();form.append('file',file);form.append('document_type',type);xhr.send(form)})
}
export async function documentBlob(tid:string,did:string){const response=await fetch(base+'/transactions/'+encodeURIComponent(tid)+'/documents/'+encodeURIComponent(did)+'/content',{credentials:'include',signal:AbortSignal.timeout(20000)});if(!response.ok)throw parseError(response.status,await response.json().catch(()=>null));return response.blob()}
