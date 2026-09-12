# 0005 — Testing the capture agent with a real camera or phone

**Date:** 2026-07-25
**Status:** Accepted

## 8. First real-hardware verification, by the founder, not a simulation

Everything up to this point in the project — the Node-driven Web Crypto proofs,
the Flask test-client regressions — was real cryptography exercised without a
real lens. On 2026-07-25 the founder ran the actual sequence on his own phone,
over this setup, for the first time: enrolled a device, captured a live photo
through the browser (not a file picker), got back a signed proof code, and
verified it — **VERIFIED CAPTURE**. He then deliberately tried the same proof
code against a *different* photo, and Veridact correctly flagged the mismatch
rather than accepting it. That second step is the one that actually matters:
it's not just that the happy path works, but that the system correctly refuses
a proof code paired with content it wasn't issued for — the exact property
decisions/0001–0003 were written to guarantee. This is the first end-to-end
confirmation of that guarantee against genuine hardware, by the person the
product is for, rather than by the same engineer who built it.

## 1. The problem

Every verification of the capture agent so far in this project has used either
the test client (no real camera involved) or a genuine browser API executed in
Node (real cryptography, but no real lens — see decisions/0004 and this
project's Nullform/Veridact test history). None of that touches an actual
camera sensor. The founder's own stated next step is to connect a real
camera — a webcam or a phone — and use the app for real. That surfaces a
concrete technical blocker worth solving deliberately rather than hitting by
surprise.

## 2. Why `getUserMedia` won't just work over the LAN

Browsers only grant camera/microphone access in a **secure context**:
HTTPS, or the specific hostnames `localhost`/`127.0.0.1`. Running
`python run.py` and opening `http://127.0.0.1:5102` on the *same machine*
already satisfies this — which is why every test so far, run from this
machine, has worked without needing HTTPS. **A phone on the same Wi-Fi
reaching this machine by its LAN IP (e.g. `http://192.168.1.23:5102`) is a
different origin, is plain HTTP, and is not a secure context** — Chrome and
Safari will silently refuse the camera permission prompt, and the failure
mode is confusing if you don't already know this rule (the page loads fine;
only the camera silently doesn't work).

## 3. What was evaluated

| Option | What it takes | Trade-off |
|---|---|---|
| **Ad-hoc self-signed cert (`ssl_context='adhoc'`)** | `pip install pyOpenSSL`, one Flask argument | Zero configuration; browser shows a "not secure" warning to click through once, every restart (a fresh cert each run) |
| **A real cert via mkcert or similar** | Install a local CA tool, generate and trust a cert | No browser warning, but adds a dependency and a one-time trust-store step per device tested from |
| **A tunneling service (ngrok, Cloudflare Tunnel)** | Third-party account/binary | Gets a real HTTPS URL with no cert warnings at all, but sends traffic through an external service for what is meant to be local-only testing |

## 3a. If your laptop has its own webcam, you don't need any of this yet

Everything below (HTTPS, LAN IPs, cert warnings) is *only* needed to reach
Veridact from a **separate device** — a phone, or a webcam on another machine.
If you just want to see the capture agent work with a real camera today,
`python run.py` and `http://127.0.0.1:5102` already satisfy the secure-context
rule on the **same machine**, no setup at all: if this laptop has a built-in
or USB webcam, **Start camera** on the Authenticate page will use it right now.
The phone-specific setup below is for testing capture from a *different*
device, which matters for the product's real-world use case (most capture
happens on phones) but isn't required to see the feature work at all.

## 4. Decision

**Use `ssl_context='adhoc'`.** It requires nothing beyond a package already
proven to install cleanly in this environment (decisions/0004), needs no
external service, and the one-time "this certificate isn't trusted" click-through
on the phone's browser is a fully acceptable cost for local testing — this is
explicitly a testing aid, not a production deployment story.

## 5. How to actually do it

```bash
cd companies/veridact
pip install -r requirements.txt
python run_phone_test.py
```

**A second real finding, from putting this in front of the founder rather
than just testing it myself:** the first version of this document told people
to set two environment variables inline (`VERIDACT_HTTPS=1
VERIDACT_HOST=0.0.0.0 python run.py`). That is **bash-only syntax** — it fails
silently confusing in PowerShell (Windows' default shell), which has no
inline-env-var form and instead tries to run a program literally named
`VERIDACT_HTTPS=1`. Recommending a shell-specific command without checking
which shell the reader is actually in was the mistake; the fix is
`run_phone_test.py` — the same two settings, hardcoded into a small script
instead of shell environment variables, so the command is identical in
PowerShell, Git Bash, or cmd.exe. `run.py`'s env-var form still exists for
anyone who wants it (documented in its own docstring), but is no longer the
first thing anyone is told to type.

**A third finding, also from testing this, not an assumption:** the first version of
this feature tried to guess the machine's LAN IP itself (opening a throwaway
UDP socket to see which interface the OS would route a packet through). On the
machine this was tested on, that guess printed a VPN adapter's address —
which does not reach a phone on the same Wi-Fi. Werkzeug (Flask's dev server)
already enumerates every bound network interface correctly when
`host="0.0.0.0"` and prints each as its own `Running on https://…` line; that
guess was removed in favor of pointing at Werkzeug's own, already-correct
output, rather than shipping a second, less reliable version of the same
information. **When you run this, use whichever printed address is your actual
Wi-Fi/LAN IP — typically `192.168.x.x` or `10.x.x.x` — not a VPN or virtual
adapter's address, which can look similar but won't be reachable from another
device.**

Open the correct `https://…` URL on a phone connected to the **same Wi-Fi
network** as the machine running Veridact. The browser will warn that the
certificate isn't trusted (expected — it's self-signed, freshly generated for
this run); accept/continue, and the camera permission prompt will now appear
correctly, because the connection is now a secure context.

## 6. What this does and doesn't prove

Testing with a real phone camera through this setup proves the whole pipeline
end-to-end against genuine hardware: real sensor → real `getUserMedia` frame →
real in-browser SHA-256 → real signature (Schnorr or ECDSA P-256, decisions/0004)
→ real server verification. It does **not** close the gap decision 0003
already states plainly: a browser still cannot distinguish this real phone
camera from a virtual camera on some *other* machine choosing to run a spoofed
video feed through the same `getUserMedia` API. Real-hardware testing confirms
the honest path works correctly; it doesn't change what the honest path can
prove.

## 7. Reducing the manual steps between enrolling and capturing

The remaining friction after fixing the two issues above wasn't technical —
it was that enrolling gives you a private key you then have to manually
copy and paste into a *different page* before you can test anything. On a
phone, copying a long JSON Web Key by hand is exactly the kind of step that
makes a test feel harder than it needs to be. Fixed: `enrol.js` now also saves
the just-enrolled `{handle, algorithm, privateKey}` to this browser's
`localStorage`, and `authenticate.js` reads it back on page load and
pre-fills both fields (visibly — a small note names which device it
restored, so nothing happens silently). It's still fully editable, and it's
the same key you're already shown and told to save yourself; this only saves
it a second time, locally, to remove the copy/paste step for the common
"just enrolled, now test" path. Verified in the actual browser page (not just
read from source): enrolling, then navigating to `/authenticate`, correctly
pre-filled both fields and showed the note.

## Trade-off

Windows Firewall may prompt to allow Python network access the first time
`VERIDACT_HOST=0.0.0.0` is used — expected, and should be allowed for the local
network only. If the phone can't reach the LAN URL at all, the two most common
causes are the two machines being on different Wi-Fi networks (e.g. one on a
guest network) or a firewall blocking the port — neither is specific to
Veridact.
