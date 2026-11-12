'use client';
import {useState,type FormEvent} from 'react';
import {api} from '@/lib/api';
export function PasswordForm({onChanged}:{onChanged:()=>void}){
 const [current,setCurrent]=useState(''),[next,setNext]=useState(''),[confirm,setConfirm]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 async function submit(e:FormEvent){e.preventDefault();setError('');if(next!==confirm){setError('New passwords do not match.');return}setBusy(true);try{await api.changePassword(current,next);setCurrent('');setNext('');setConfirm('');onChanged()}catch(e){setError(e instanceof Error?e.message:'Password change failed.')}finally{setBusy(false)}}
 return <form onSubmit={submit}><h3>Change password</h3><p className="small muted">Use 12–256 characters. A successful change signs out all sessions. Sign in again with your new password.</p><label>Current password<input type="password" required autoComplete="current-password" maxLength={256} value={current} onChange={e=>setCurrent(e.target.value)}/></label><label>New password<input type="password" required autoComplete="new-password" minLength={12} maxLength={256} value={next} onChange={e=>setNext(e.target.value)}/></label><label>Confirm new password<input type="password" required autoComplete="new-password" minLength={12} maxLength={256} value={confirm} onChange={e=>setConfirm(e.target.value)}/></label>{error&&<p role="alert">{error}</p>}<button className="primary" disabled={busy}>{busy?'Changing password…':'Change password and sign out'}</button></form>
}
