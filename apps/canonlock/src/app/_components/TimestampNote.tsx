export function TimestampNote() {
  return (
    <section className="border-b border-border px-6 py-section">
      <div data-reveal className="mx-auto max-w-data">
        <p className="font-mono text-step--1 uppercase tracking-widest text-accent">The timestamp</p>
        <p className="mt-3 max-w-prose text-step-0 text-muted">
          Every seal attempts a real RFC 3161 request to an independent time-stamp authority — a
          second party, outside this server, backing the moment with its own clock. It is
          best-effort: when the authority can&rsquo;t be reached, the certificate says so outright.
          It says <span className="font-mono text-warn">unavailable</span>, with the reason, rather
          than inventing a token that was never granted.
        </p>
      </div>
    </section>
  );
}
