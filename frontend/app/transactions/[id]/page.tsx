import {Suspense} from 'react';
import Dashboard from '@/components/dashboard';
async function Detail({params}:{params:Promise<{id:string}>}){const {id}=await params;return <Dashboard initialTransaction={id}/>}
export default function Page({params}:{params:Promise<{id:string}>}){return <Suspense fallback={<main className="center-screen">Loading transaction workspace…</main>}><Detail params={params}/></Suspense>}
