import { GUIDE } from "./guide";
export default function UserGuide() {
  return <div className="mx-auto max-w-4xl space-y-6 px-6 py-6">
    <div><h1 className="font-heading text-2xl font-semibold">User guide</h1>
      <p className="text-sm text-muted-foreground">A short, friendly tour of Neurealm Service Desk by Neurealm. We hope it helps — tell us what's missing.</p></div>
    <nav aria-label="Guide sections" className="flex flex-wrap gap-2">{GUIDE.map((g) => <a key={g.id} href={`#${g.id}`} className="rounded-full border px-3 py-1 text-xs hover:bg-muted">{g.title}</a>)}</nav>
    {GUIDE.map((g) => <section key={g.id} id={g.id} className="rounded-xl border bg-card p-5">
      <h2 className="font-heading text-lg font-semibold">{g.title}</h2><p className="mb-2 text-xs text-muted-foreground">For: {g.who}</p>
      <ol className="list-decimal space-y-1 ps-5 text-sm">{g.steps.map((s) => <li key={s}>{s}</li>)}</ol></section>)}
  </div>;
}
