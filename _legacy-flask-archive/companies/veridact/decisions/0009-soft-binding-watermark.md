# 0009 — Soft-binding watermark: TrustMark, so recompression doesn't read as tampering

**Date:** 2026-08-02
**Status:** Accepted (2026-08-03) — see §10 for OTT's answers to the three open questions

## 1. The problem

Verification today is "hard binding" only: an exact SHA-256 of the file's bytes. That's
the strongest possible proof, but it breaks the moment a file is recompressed — which
happens constantly in real use, especially in exactly the high-stakes cases (legal
evidence, journalism, human-rights documentation) this project cares most about. Right
now that shows up as **ALTERED**, which wrongly implies tampering when nothing malicious
happened. This is a known, industry-wide problem, not a Veridact-specific bug — even
C2PA credentials from Leica/Sony/Nikon cameras get stripped the same way by Instagram
and X, which is exactly why OpenAI pairs C2PA metadata with a watermark in the first
place: metadata alone isn't durable enough.

## 2. What was surveyed

| Option | What it is | Robust to resize? | Dependency weight | Fit |
|---|---|---|---|---|
| **`invisible-watermark`** (ShieldMnt/Stability-AI) | Classical DWT-DCT / DWT-DCT-SVD / RivaGAN frequency-domain watermarking; `dwtDctSvd` is what Stable Diffusion ships | **No** — the library's own docs state it is not robust to resize or aspect-ratio-changed crop | Light: OpenCV + numpy only for the DCT methods, no GPU/deep-learning runtime | Passes JPEG-recompression tests, but **fails the actual named threat model**: WhatsApp resizes images to a ~1600px long edge in addition to recompressing (verified via current WhatsApp compression documentation, not assumed), so this would silently stop working on exactly the case this decision exists to fix. |
| **TrustMark** (`adobe/trustmark`) | A DNN-based invisible watermark built by Adobe **for the Content Authenticity Initiative** — the same organization behind the C2PA spec and `c2pa-python`, already a dependency of this project (`app/c2pa_check.py`) | Yes — explicitly trained to survive "non-editorial transformations... that occur when images are reshared online," and is CAI's own documented mechanism for exactly this problem, called a **"Durable Content Credential via soft binding"** in their own docs | Heavy: PyTorch runtime, model weights auto-downloaded on first use | **Purpose-built for this exact problem, by the same standards body whose read-side library this project already trusts** — not a generic watermarking tool being repurposed. |
| **RivaGAN** (bundled inside `invisible-watermark`) | Deep-learning encoder/decoder trained on the Hollywood2 movie-clips dataset | Passes the library's own JPEG test, resize untested/unclaimed | Heavy (its own DNN runtime) without TrustMark's CAI/C2PA alignment | Rejected — no protocol-level tie to C2PA/soft-binding, and the library's own docs call it 10x slower with no accuracy guarantee even absent an attack. |

**Recommendation: TrustMark.** It is the official, purpose-built companion to the C2PA
library this project already depends on, from the same standards organization, solving
precisely the "soft binding" problem this decision is named after (that is CAI's own
term for it, independently arrived at the same name the founder used in the original
brief for this work). `invisible-watermark` was the lighter-weight alternative but is
disqualified by a concrete, sourced fact: it doesn't survive resizing, and WhatsApp
resizes.

## 3. A real reliability concern, found and designed around — not ignored

Independent research (Hacker Factor, a digital-forensics research blog with a long
track record analyzing image-provenance tools) reports a **10–20% false-positive rate**
on certain structured image content — photos of grid-like patterns (graph paper, BIOS
menus, spreadsheets) cause TrustMark's decoder to report a watermark is "present" with a
degenerate, all-zero payload, even on images that were never watermarked. The same
report notes the Python and Rust reference implementations disagree on some inputs,
suggesting the decoder is numerically sensitive rather than a robust binary "is/isn't
watermarked" signal on its own.

**This matters a great deal for a truth-infrastructure product**: decisions/0001 is
built on the principle that Veridact never claims something is real when it can't back
that up. A "watermark detected" signal alone, taken at face value, could cause a file
that was never captured through Veridact to be told it was — a false positive is a much
worse failure than a false negative here, because a false negative just falls back to
today's honest UNVERIFIED/ALTERED verdicts.

**The mitigation is not "trust the decoder's `present` flag."** It is the same pattern
CAI's own documentation describes for soft binding: TrustMark's payload is a **random
identifier embedded specifically to be looked up against a database** — not a
self-describing signature. Veridact will:

1. Generate a random, high-entropy secret (not the human-facing manifest ID itself —
   see §5, §7) at capture time and store it against that manifest, server-side.
2. At verify time, only trust a watermark result if the **decoded payload exactly
   matches** an issued secret on file (§6's decode-then-lookup design). A presence-only
   "yes/no" from the decoder is never sufficient on its own.

A spurious "all-zero" or otherwise degenerate decode from an unrelated grid-pattern
image would have to coincidentally match one specific, randomly-issued 56-bit value
already on file (§7) — not "look plausible," but match exactly. That is not something
the documented failure mode does; it collapses toward a fixed zero state, not toward
arbitrary previously-issued secrets. This converts a real, sourced reliability concern
into a manageable one by construction, rather than writing it off.

## 4. Decision

Adopt **TrustMark** (`pip install trustmark`, MIT-licensed, Adobe's official CAI
implementation) as the soft-binding watermark, embedded server-side immediately after a
capture is signed and accepted.

## 5. What changes architecturally — the image reaches the server once, and it must happen *before* signing, not after

Today, the captured image's bytes never leave the browser (decisions/0003) — only the
hash and signature (the manifest) are sent to `/attest`. TrustMark's encode/decode is a
Python library with no browser-side equivalent used here, so embedding it requires the
image to be sent to the server exactly once.

**A real design mistake, caught before writing any code, not after:** the first draft of
this section had the image embedded *after* `/attest`, on the already-signed bytes. That
doesn't work — watermarking necessarily changes the pixel bytes, so if the signed hash
is taken *before* watermarking, **the saved file's hash can never exactly match what was
signed again, for any capture, ever** — the strongest verdict (VERIFIED_CAPTURE) would
become unreachable the moment embedding is automatic on every capture (§10), because
every single saved file, including ones nobody ever shared or recompressed, would
immediately register as RECOMPRESSED instead. Tracing that through before implementing
is what caught it.

**Corrected order: watermark, then hash, then sign.** The capture flow becomes:

1. Browser captures the live frame into memory (unchanged — still no file picker).
2. Browser sends the **raw, unsigned** frame to a new endpoint, `POST /capture/watermark`,
   which generates a fresh random secret, embeds it via TrustMark, and returns the
   watermarked image bytes plus the secret (hex-encoded).
3. Browser hashes the **watermarked** bytes — this is the hash that gets signed.
4. Browser requests the freshness challenge and signs (unchanged crypto, decisions/0002/0004)
   — just now signing the watermarked file's hash instead of the pre-watermark one.
5. Browser calls `/attest` as today, now also including the secret from step 2, which
   `/attest` stores directly on the new manifest row in the same insert (no separate
   embed-after-attest step is needed).

**Why this still doesn't reopen the gap decisions/0001/0003 closed.** `/capture/watermark`
is a generic, unauthenticated "embed a random secret into this image" utility, and that
alone proves nothing and grants no capability — the only thing that ever produces a
VERIFIED_CAPTURE verdict is a valid device signature, completely unchanged from today,
which nobody can produce without the enrolled device's private key. Someone could call
this new endpoint with an AI-generated image and get a secret embedded in it, but that
secret means nothing until it's *also* attached to a manifest row — which only happens
inside `/attest`, gated by the exact same signature check as always. Without a valid
signature, the secret sits in no manifest, and the decode-then-lookup in §6 finds no
match at verify time. The image still has to reach the server once, earlier than before
— but attestation, the actual trust boundary, is untouched.

The secret is generated fresh per capture and is never the manifest ID itself (which is
already public, printed on the result screen, and would be a low-entropy, guessable
payload if reused directly as the watermark secret).

## 6. The new verdict

A fourth verdict, distinct from the existing three (decisions/0001):

| Verdict | Meaning |
|---|---|
| **RECOMPRESSED** | The exact hash doesn't match what was signed, but a watermark exactly matching this manifest's secret was found. The content is very likely the same as what was captured — it was just re-encoded (recompression, resize, format conversion) somewhere between capture and this check. |

`verify()`'s order becomes: try the exact hash (VERIFIED_CAPTURE / SIGNATURE_INVALID,
unchanged) → if no exact match, **decode whatever watermark payload is present (if any)
and look it up directly against the table of issued secrets** → if that lookup matches
a manifest, RECOMPRESSED → only then, if a manifest_id was separately supplied, ALTERED
→ only then UNVERIFIED. RECOMPRESSED is honestly weaker evidence than VERIFIED CAPTURE
(it can't prove the exact bytes), and honestly stronger/different information than
ALTERED (which currently conflates "recompressed" with "actually edited or forged" —
precisely the confusion this whole piece of work exists to remove).

**Refinement made at sign-off, not in the original draft:** decode-then-lookup-by-value,
rather than requiring the person verifying to already have a manifest_id. A file that's
been through WhatsApp has typically lost its embedded PNG metadata (decisions/0008) along
with everything else — if RECOMPRESSED only worked when a manifest_id was separately
supplied, it would reintroduce exactly the "you need a code, not just the file" friction
Phase 1 removed, for precisely the case (recompressed sharing) this phase exists to
handle. Looking up the decoded value directly means RECOMPRESSED works from the file
alone, no code required. This does mean an unrelated file's spurious decode gets checked
against every issued secret rather than one specific manifest's — see §3's exact-match
math for why that's still not a meaningful risk at realistic table sizes.

## 7. Payload and storage — a real gotcha found by testing, not assumed

TrustMark's `secret_len=100` is the *total* packet size (data + BCH error-correction +
4 version bits), not the usable payload. Reading the actual shipped implementation
(`trustmark/datalayer.py`) rather than assuming from the headline number: the default
scheme (`BCH_5`) carries **61 usable data bits**, not 100. Passing a longer string is
**not rejected** — `process_encode` silently truncates/zero-pads to fit
(`packet_d=packet_d[0:data_bitcount]`). Caught this exact way, not in theory: an
initial test encoding the 14-character string `'VD-TESTSECRET1'` (112 bits) in the
library's default text mode decoded back as the garbled `'VD-TESTSD'` — a silent
corruption, not an error, that would have been a real, confusing production bug if the
payload design had used a human-readable string without checking its bit length first.

**Decision:** use TrustMark's `MODE='binary'` API with a **56-bit (7-byte) random
secret** — comfortably under the 61-bit cap, byte-aligned, and generated fresh
server-side per manifest (never the human-facing manifest ID, which is already public
and low-entropy by comparison). New column: `manifests.watermark_secret` (a 7-byte
value, nullable — only captures processed through the new embed step have one; nothing
already captured is retroactively affected).

## 8. Real robustness results — verified against actual files, both ways

All of the following were run against the running install, not assumed from the
library's own documentation:

| Test | Result |
|---|---|
| Exact round trip (encode → decode, no transform) | **Pass** — decoded 56 bits match exactly |
| Negative control (decode a never-watermarked photo) | **Pass** — correctly reports absent |
| JPEG recompress only, same resolution, quality 90/80/60 | **Pass** at all three — exact 56-bit match |
| Resize to a 1600px long edge + JPEG q80 (mimics WhatsApp's actual pipeline, confirmed via current WhatsApp compression documentation) | **Pass** — exact 56-bit match |

**One real false start worth recording:** the very first pass of this testing used a
64×64-pixel synthetic test image and found recompression-only *failed* while
resize+recompress *passed* — a confusing, backwards-looking result. Re-running against
a realistic photo resolution (2048×1365, the official C2PA test fixture already used by
`c2pa_check.py`) passed every case cleanly. The 64×64 result was an artifact of testing
at a non-representative resolution (a real capture from `getUserMedia` is at minimum
1280×720, decisions/0003), not a real robustness gap — **but it's a reminder to keep
testing this against realistic capture sizes going forward**, not small fixtures chosen
for speed.

Not tested here (still a real, open risk, not swept under the rug): the specific
grid-pattern false-positive failure mode from §3's independent research. That failure
mode is about spurious *presence* detection on structured content that was never
watermarked at all — the exact-secret-match mitigation in §3 addresses it by
construction, but it hasn't been reproduced and verified directly against a real grid-
pattern image the way the recompression cases above were. Worth doing before shipping,
noted honestly rather than assumed fixed.

## 9. A real environment conflict, found and resolved

`pip install trustmark` downgraded this machine's shared Python environment's `numpy`
from 2.5.1 to 1.26.4 to satisfy a `numpy<2.0.0` pin in TrustMark's own metadata — which
pip flagged as breaking four other already-installed packages in this same environment
(`opencv-python-headless`, `pandas`, `scipy`, `tifffile`, all of which require
`numpy>=2`). This is a shared, non-virtualenv'd Python install, so this would have been
a real regression to whatever else on this machine depends on those packages.

**Resolved, and verified, not just reverted and hoped:** upgraded numpy back to 2.5.1
and re-ran the full test battery in §8 again — TrustMark's own `numpy<2.0.0` pin turned
out to be overly conservative: every encode/decode/robustness test above passed
identically under numpy 2.5.1, and `pandas`, `scipy`, `tifffile`, `opencv-python-headless`,
and `c2pa-python` were all re-confirmed working normally. **This project's
`requirements.txt` should pin `numpy>=2` explicitly** once this ships, so a future
`pip install -r requirements.txt` in a fresh environment doesn't quietly repeat this
downgrade.

One more real number worth recording for anyone deploying this: TrustMark's first use
downloads its model weights and loads them, which took **~200 seconds** in this
environment on first download — a one-time cost per process, not per request, but a
real cold-start consideration.

**Cut down, and verified, not just assumed reducible:** most of that 200s was network
download of model files (this environment's own documented history of slow large
downloads, decisions/0004), not load time — once cached on disk, loading dropped to
**55.4s**. TrustMark also loads two models Veridact never uses: a watermark *remover*
and a bounding-box *detector* (both irrelevant here — Veridact only encodes and
decodes). Passing `loadRemover=False, loadBBoxDetector=False` cuts the cached load to
**16.9s**, with encode/decode re-verified working correctly afterward (exact-match
round trip, same as §8). Combined with loading the model once at server startup rather
than per-request (already the plan), the per-capture cost users actually feel is just
the encode time — **~0.7s**, not the load time at all.

## 10. Resolved at sign-off (2026-08-03)

1. **TrustMark's footprint is acceptable, conditional on the results being real** — which
   §8's verified round-trip and recompression/resize tests confirm they are. The
   ~200s concern is substantially addressed by the finding above (17s cached load,
   almost entirely amortized at server startup, not per capture).
2. **The exact-secret-match mitigation (§3, refined in §6) is confirmed sufficient** —
   no second independent signal required. RECOMPRESSED requires an exact match against
   a specific, randomly-issued secret; the documented false-positive mode produces a
   fixed degenerate value, not an arbitrary one, making a coincidental match
   astronomically unlikely at any realistic table size.
3. **Embedding happens automatically on every capture** — no separate opt-in "prepare
   for sharing" step. `/attest` gains a watermark-embed pass as part of its normal
   response, not a distinct user action.

## 11. Relationship to the rest of this project

This is **interoperability's opposite number**: decisions/0007 made Veridact able to
*read* another system's durability mechanism (C2PA); this makes Veridact *emit* its own.
It is unrelated to the separate C2PA-*writing* work (embedding a real C2PA manifest at
capture time) — that is a distinct piece of work with its own decision doc, addressing
being readable by outside tools, not surviving recompression. An embedded C2PA
manifest is stripped by lossy resharing exactly like a Leica's is; this watermark is
what's still there afterward. The two are complementary, not overlapping.
