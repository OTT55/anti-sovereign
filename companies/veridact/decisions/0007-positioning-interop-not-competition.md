# 0007 — Positioning: interoperate with C2PA, target an underserved niche

**Date:** 2026-07-25
**Status:** Accepted

## 1. The problem

Live market research (research/13) surfaced a fact that changes Veridact's
strategic footing: the exact problem it solves in software — sign a capture so
its origin can be proven — is now being solved **in hardware**, by every major
camera manufacturer (Leica, Sony, Nikon, Canon, Samsung), under one converging
standard: **C2PA**. Truepic, a C2PA founding member, has raised $39.1M with
Microsoft/Adobe/Sony's venture arms behind it. Competing with "we can sign a
photo" as the whole pitch means competing with a free, hardware-level standard
backed by the industry's largest players.

The founder was also right that "law/legal evidence" is a real, validated
destination for this technology — eyeWitness to Atrocities (International Bar
Association, since 2015) has had its footage used in actual Ukrainian court
cases. But that specific niche already has a credible, decade-old nonprofit
incumbent with real courtroom history.

## 2. Decision

**Veridact repositions around two commitments, chosen by the founder directly
from the research:**

1. **Interoperate with C2PA rather than compete with it.** Veridact's own
   signing (Schnorr/ECDSA, decisions/0002/0004) remains the *bridge* for
   devices without hardware C2PA support — still a real, useful role, since
   most phones don't have it yet — but Veridact's Verify page should also be
   able to **read and validate a real C2PA manifest** from hardware that
   already signs (a Leica, a Sony camera, a Samsung Galaxy S26). This is an
   engineering commitment, tracked separately as it's scoped (see the research
   note on library feasibility, checked live rather than assumed).
2. **Target an underserved vertical, not the funded incumbents' lanes.**
   Not insurance/lending (Truepic's actual market), not international
   human-rights documentation (eyeWitness's established, mission-funded
   territory) — but smaller, currently-unserved users who need "good enough
   for court" verification and aren't served by either: independent
   investigators, small law firms, or an individual documenting a personal
   dispute (a landlord/tenant issue, a workplace incident, a small claim).

## 3. Why this over the alternatives considered

- **"Keep building our own scheme, pitch broadly"** was rejected: it means
  competing directly with a $39M-funded standard on the standard's own turf
  (proving a capture is genuine), with no differentiated angle.
- **"Treat this purely as a portfolio piece"** was considered and is still the
  honest fallback if the niche doesn't pan out — nothing about pursuing a real
  niche first forecloses that; a well-executed real attempt *is* the stronger
  portfolio piece, not a distraction from it.

## 4. Feasibility check on the C2PA library, and an environment-specific blocker (2026-07-25)

The plan in §3 depends on using an official library rather than hand-parsing
the JUMBF/COSE format. Checked directly rather than assumed:

- **The mechanism lines up well with work already done.** C2PA's own
  specification recommends ES256 (ECDSA on P-256) as a primary signing
  algorithm — the exact scheme this project added in decisions/0004, for
  independent reasons. That's a good sign for eventual interop, not a
  coincidence to rely on blindly, but worth noting.
- **`c2pa-python`** (official, maintained by the C2PA organisation's
  `contentauth` GitHub org) is the right tool for reading/verifying real
  manifests — confirmed via its PyPI listing and source repository, not
  assumed from the library's name alone.
- **This specific sandboxed environment cannot complete the install.** The
  wheel is 87.5MB (it bundles a compiled Rust binary per platform). Two
  separate attempts — including pip's own automatic resume-on-timeout
  logic — both failed with `IncompleteRead`/`ProtocolError` after making it
  partway through (52MB and 20MB respectively) before the connection broke
  for good. This reads as a real bandwidth/stability constraint of this
  sandbox specifically, not a problem with the package, the plan, or this
  machine's normal network — a large one-off binary download is a different
  load pattern than the small packages (`cryptography`, `pyOpenSSL`, `fido2`)
  that installed cleanly earlier in this project. **Next step: install
  `c2pa-python` on a normal (non-sandboxed) machine** — expected to be
  straightforward there — before continuing this integration.

## 5. The C2PA interop feature, built and verified (2026-07-25)

Once `c2pa-python` was actually installed (§4's blocker was resolved with a
resumable `curl -C -` download after pip's own retry logic failed twice on
this environment's connection), the read/verify side of §2's plan was built
and verified for real, not left as a research note:

- **`app/c2pa_check.py`** wraps `c2pa.Reader` and returns a plain, serializable
  summary — never the library's raw objects, so the JSON response shape
  doesn't depend on the library's internals.
- **`POST /api/verify/c2pa`** — a new, deliberately separate route from the
  existing `/api/verify`. It takes an actual file upload, not a hash, because
  a C2PA manifest lives *inside* the file's own container — there is no way
  to check it from a hash alone. Veridact's own scheme's no-upload property
  (decisions/0001, 0003) is unchanged; this is a second, clearly distinct
  check, not a weakening of the first.
- **The Verify page** now has a second section, "check for a camera's own
  credential," wired to this route.

**Verified against real data, at every layer** — the module directly, the
HTTP route via the Flask test client, and the actual browser page driving the
real upload button — using `contentauth/c2pa-python`'s own official test
fixture (`C.jpg`, a genuinely C2PA-signed test image from that project's test
suite, fetched with the founder's explicit approval since it required
downloading a file):

| Input | Result |
|---|---|
| The real signed test image | `Valid` — reports the real signing certificate ("C2PA Test Signing Cert"), algorithm (Ps256), and timestamp (2023-09-29) |
| The same image with one byte of pixel data flipped | `Invalid`, with the specific reason `assertion.dataHash.mismatch — Hashes do not match` |
| An ordinary photo with no C2PA data at all | Handled cleanly as "no manifest" — the library's `ManifestNotFound` exception, not a crash |

**One honest, precise note on the tampered result:** it also reported
`signingCredential.untrusted`. That's expected and correct, not a flaw — the
test fixture is signed by a C2PA *test* certificate, which is not in a
production trust list. It would be worth checking whether the *unmodified*
original also reports this once the answer matters for a real deployment (it
did not in this test, likely because the library's default settings didn't
independently flag the test cert until the claim was already invalidated by
the hash mismatch) — trust-list configuration for a real deployment is a
distinct, separate piece of work from what's verified here, which is
specifically the tamper-detection property.

## Trade-off

This is a real scope increase over "sign captures in a browser": reading
someone else's manifest format correctly, forever, as that format evolves
(C2PA is at v2.2 with v2.3 in progress) is an ongoing commitment, not a
one-time integration. The mitigating factor: the C2PA organization itself
publishes and maintains official parsing/verification libraries (`c2pa-rs`,
`c2pa-python`, `c2pa-js`) — the plan is to use one of these directly rather
than hand-parse the JUMBF/COSE format, which would be exactly the kind of
"invent your own crypto/parsing" mistake this project has otherwise avoided
throughout (Merkle proofs, Schnorr, ECDSA all lean on established primitives
or, where custom, are clearly labelled as such).
