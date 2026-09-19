export function ProofClaims() {
  return (
    <section className="border-b border-border px-6 py-section">
      <div data-reveal className="mx-auto grid max-w-data gap-8 md:grid-cols-2">
        <div>
          <p className="font-mono text-step--1 uppercase tracking-widest text-accent">
            What this proves
          </p>
          <ul className="mt-4 max-w-prose space-y-2 text-step-0 text-text">
            <li>This exact file existed, unedited, no later than the moment you sealed it.</li>
            <li>
              Its position in the record is fixed by every hash appended after it — moving or
              deleting it would change the root.
            </li>
            <li>An independent timestamp, when one is reachable, backs the moment with a third party.</li>
          </ul>
        </div>
        <div>
          <p className="font-mono text-step--1 uppercase tracking-widest text-muted">
            What this does not prove
          </p>
          <ul className="mt-4 max-w-prose space-y-2 text-step-0 text-muted">
            <li>Not authorship — only that this file, this hash, existed by this time.</li>
            <li>Not ownership, and not a copyright filing.</li>
            <li>Not a blockchain — one server, one append-only log, independently checkable math.</li>
            <li>Nothing here stops anyone from copying your work. It only fixes when you had it.</li>
          </ul>
        </div>
      </div>
    </section>
  );
}
