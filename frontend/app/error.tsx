"use client";
export default function ErrorPage({ reset }: { error: Error & { digest?: string }; reset: () => void }) { return <main className="not-found"><div className="section-kicker">THE ROOM NEEDS A MOMENT</div><h1>We couldn’t load this view.</h1><p>Your case data is safe. Try loading the view again.</p><button className="button-primary" onClick={reset}>Try again ↻</button></main>; }
