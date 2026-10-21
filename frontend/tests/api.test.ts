import {describe,it,expect,vi,afterEach} from 'vitest';
import {request,setCsrf,parseError} from '@/lib/api';
afterEach(()=>vi.unstubAllGlobals());
describe('API client security',()=>{
 it('does not reflect secrets from backend errors',()=>{expect(parseError(500,{error:{code:'UNKNOWN',message:'secret-value'}}).message).not.toContain('secret-value')});
 it('sends credentials and the session CSRF token for mutations',async()=>{const fetch=vi.fn().mockResolvedValue({ok:true,json:async()=>({status:'ok'})});vi.stubGlobal('fetch',fetch);setCsrf('synthetic-csrf');await request('/example',{method:'POST',body:'{}'});expect(fetch).toHaveBeenCalledWith('/api/v1/example',expect.objectContaining({credentials:'include',headers:expect.objectContaining({'X-CSRF-Token':'synthetic-csrf'})}))});
 it('sanitizes network exception details',async()=>{vi.stubGlobal('fetch',vi.fn().mockRejectedValue(new Error('private-token')));await expect(request('/example')).rejects.toThrow('Cannot reach the backend')});
});
