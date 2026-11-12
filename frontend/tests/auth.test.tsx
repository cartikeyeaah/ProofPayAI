import {it,expect,vi} from 'vitest';
import {render,screen,fireEvent,waitFor} from '@testing-library/react';
import {PasswordForm} from '@/components/password-form';
import {api,parseError} from '@/lib/api';
it('requires matching passwords and signs out after a successful change',async()=>{
 const changed=vi.fn(); const call=vi.spyOn(api,'changePassword').mockResolvedValue({status:'logged_out'});
 render(<PasswordForm onChanged={changed}/>);
 fireEvent.change(screen.getByLabelText('Current password'),{target:{value:'Old-synthetic-password'}});
 fireEvent.change(screen.getByLabelText('New password',{exact:true}),{target:{value:'New-synthetic-password'}});
 fireEvent.change(screen.getByLabelText('Confirm new password'),{target:{value:'Mismatch-password'}});
 fireEvent.click(screen.getByRole('button'));expect(screen.getByRole('alert')).toHaveTextContent('do not match');expect(call).not.toHaveBeenCalled();
 fireEvent.change(screen.getByLabelText('Confirm new password'),{target:{value:'New-synthetic-password'}});
 fireEvent.click(screen.getByRole('button'));await waitFor(()=>expect(changed).toHaveBeenCalledOnce());expect(call).toHaveBeenCalledWith('Old-synthetic-password','New-synthetic-password');call.mockRestore();
});
it('signals expired sessions but does not log out on wrong current password',()=>{
 const listener=vi.fn();window.addEventListener('proofpay:session-expired',listener);
 parseError(401,{error:{code:'INVALID_PASSWORD'}});expect(listener).not.toHaveBeenCalled();
 parseError(401,{error:{code:'AUTH_REQUIRED'}});expect(listener).toHaveBeenCalledOnce();window.removeEventListener('proofpay:session-expired',listener);
});
