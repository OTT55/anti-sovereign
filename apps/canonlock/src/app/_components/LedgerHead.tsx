import { LiveRoot } from "./LiveRoot";

export function LedgerHead() {
  return (
    <section className="border-b border-border px-6 py-section-lg">
      <div className="mx-auto max-w-data">
        <p className="font-mono text-step--1 uppercase tracking-widest text-accent">Canonlock</p>
        <h1 className="mt-4 max-w-narrow font-display text-step-5 font-semibold leading-[1.05] text-text">
          You cannot prove you made it first.
          <br />
          You can prove it already existed.
        </h1>
        <div className="mt-8">
          <LiveRoot />
        </div>
      </div>
    </section>
  );
}
