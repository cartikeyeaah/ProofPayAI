import Link from "next/link";
export default function NotFound() { return <main className="not-found"><div className="section-kicker">CASE FILE NOT FOUND</div><h1>This record isn’t in the room.</h1><p>Check the transaction ID or return to the dashboard.</p><Link className="button-primary" href="/dashboard">Return to dashboard →</Link></main>; }
