import type {Metadata} from 'next';
import './globals.css';
export const metadata:Metadata={title:'ProofPay AI — Merchant workspace',description:'Private payment evidence intelligence. Source-backed findings and merchant-reviewed drafts.'};
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="en"><body><a className="skip-link" href="#main-content">Skip to main content</a>{children}</body></html>}
