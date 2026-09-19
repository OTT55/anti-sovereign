"use client";

import { useEffect, useState } from "react";
import { foldLevels, textToHashHex } from "../_lib/demoHash";

const SAMPLE_LABELS = ["alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel"];
const HEX = "0123456789abcdef";
const ROW_LABELS = ["8 leaves", "4 pairs", "2 pairs", "the root"];

export function FoldSequence() {
  const [leaves, setLeaves] = useState<string[] | null>(null);
  const [levels, setLevels] = useState<string[][] | null>(null);
  const [tamperIndex, setTamperIndex] = useState<number | null>(null);
  const [tamperedLevels, setTamperedLevels] = useState<string[][] | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all(SAMPLE_LABELS.map(textToHashHex)).then(async (hashes) => {
      if (cancelled) return;
      setLeaves(hashes);
      setLevels(await foldLevels(hashes));
    });
    return () => {
      cancelled = true;
    };
  }, []);

  async function tamperLeaf(index: number) {
    if (!leaves) return;
    const current = leaves[index]!;
    const nextChar = HEX[(HEX.indexOf(current[0]!) + 1) % HEX.length];
    const nextHash = nextChar + current.slice(1);
    const nextLeaves = leaves.map((h, i) => (i === index ? nextHash : h));
    setTamperIndex(index);
    setTamperedLevels(await foldLevels(nextLeaves));
  }

  function reset() {
    setTamperIndex(null);
    setTamperedLevels(null);
  }

  return (
    <section className="border-b border-border px-6 py-section">
      <div className="mx-auto max-w-data">
        <p className="font-mono text-step--1 uppercase tracking-widest text-accent">The fold</p>
        <p className="mt-3 max-w-prose text-step-1 text-muted">
          A worked example — eight sample files, not real registry entries. Your file never moves;
          only its 64-character hash does. Each pair is hashed together. An odd node is paired with
          itself. One number ends up standing for the whole set.
        </p>

        {!levels ? (
          <p className="mt-10 font-mono text-step--1 text-muted">Folding…</p>
        ) : (
          <div className="mt-10 space-y-6">
            {levels.map((level, li) => (
              <FoldRow
                key={li}
                label={ROW_LABELS[li]!}
                hashes={level}
                tamperedHashes={tamperedLevels?.[li] ?? null}
                interactive={li === 0}
                onTamper={li === 0 ? tamperLeaf : undefined}
                tamperIndex={li === 0 ? tamperIndex : null}
              />
            ))}
          </div>
        )}

        {tamperIndex !== null && (
          <div className="mt-6 flex flex-wrap items-center gap-4">
            <p className="text-step--1 text-danger">
              Leaf {tamperIndex} changed by one hex character — the root above no longer matches.
              Change one byte, and the fold disproves itself.
            </p>
            <button
              type="button"
              onClick={reset}
              className="shrink-0 rounded-xs border border-border px-3 py-1.5 font-mono text-step--1 text-muted transition-colors duration-fast hover:border-accent hover:text-text"
            >
              Reset
            </button>
          </div>
        )}
      </div>
    </section>
  );
}

function FoldRow({
  label,
  hashes,
  tamperedHashes,
  interactive,
  onTamper,
  tamperIndex,
}: {
  label: string;
  hashes: string[];
  tamperedHashes: string[] | null;
  interactive: boolean;
  onTamper?: (index: number) => void;
  tamperIndex: number | null;
}) {
  return (
    <div data-reveal className="flex flex-wrap items-center gap-3">
      <span className="w-20 shrink-0 font-mono text-step--1 text-muted">{label}</span>
      <div className="flex flex-1 flex-wrap gap-2">
        {hashes.map((hash, i) => {
          const tampered = tamperedHashes?.[i];
          const isTamperedLeaf = tamperIndex === i && interactive;
          const content = tampered ? (
            <DiffHex original={hash} current={tampered} />
          ) : (
            <>
              <span className="text-text">{hash.slice(0, 16)}</span>
              <span className="text-muted">…</span>
            </>
          );

          if (!interactive) {
            return (
              <span
                key={i}
                className="rounded-xs border border-border/60 px-2 py-1 font-mono text-step--1"
              >
                {content}
              </span>
            );
          }

          return (
            <button
              key={i}
              type="button"
              onClick={() => onTamper?.(i)}
              title="Alter this leaf by one hex character"
              className={`rounded-xs border px-2 py-1 font-mono text-step--1 transition-colors duration-fast hover:border-accent ${
                isTamperedLeaf ? "border-danger" : "border-border"
              }`}
            >
              {content}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function DiffHex({ original, current }: { original: string; current: string }) {
  const chars = current.slice(0, 16).split("");
  return (
    <>
      {chars.map((c, i) => (
        <span key={i} className={c === original[i] ? "text-text" : "text-danger"}>
          {c}
        </span>
      ))}
      <span className="text-muted">…</span>
    </>
  );
}
