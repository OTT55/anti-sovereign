# 0006 — Veridact as an installable PWA, not (yet) a native app

**Date:** 2026-07-25
**Status:** Accepted

## 1. The problem

The founder asked for Veridact to become "its own camera" — something that
feels like a dedicated app, not a website you happen to navigate a browser to.
Market research (research/13) confirmed this is the right instinct: Serelay,
a funded competitor in this exact space, ships precisely this as its "Idem"
product.

## 2. What was evaluated

| Option | What it takes | Trade-off |
|---|---|---|
| **Progressive Web App (PWA)** | A manifest file, icons, some `<meta>` tags | Days not weeks; no app-store review; still fundamentally a website, which is honest about what it is |
| **Native app (Swift/Kotlin or React Native)** | New toolchains, app-store developer accounts, real device testing | Feels most "real," but is a much larger commitment — weeks, not days, and this project has no native-mobile tooling set up yet |

## 3. Decision

**PWA first.** It directly delivers what was asked — an installable home-screen
icon that opens full-screen, no browser chrome, using the phone's actual
camera — with the app-factory/Flask/HTML stack already built and already
verified working end-to-end on real hardware (decisions/0005). Native is the
right call *if* this gets real traction and needs things a PWA can't do
(background capture, deeper OS integration) — not a default first step.

## 4. What was actually built

- `static/manifest.webmanifest` — name, start URL (`/authenticate`, since
  that's the camera experience, not the enrolment page), `display: standalone`,
  icons.
- Four icons generated programmatically (Pillow, not a design tool) in
  Veridact's existing brand colours: a dark rounded-square background with a
  simple ring-and-dot glyph in the accent blue — legible at small sizes,
  distinct from a photo/camera cliché. 192px and 512px standard, a 512px
  **maskable** variant (extra safe-zone padding so Android's adaptive-icon
  crop doesn't clip it), and a 180px `apple-touch-icon` for iOS.
- `base.html` now links the manifest and sets the iOS-specific meta tags
  (`apple-mobile-web-app-capable`, status bar style, touch icon) alongside the
  standard `theme-color`.
- **Verified, not assumed:** booted a live instance and confirmed the manifest
  is served with the correct `application/manifest+json` content-type (not
  every system's default MIME map has `.webmanifest` registered — checked
  directly via the real HTTP response header rather than trusting the Python
  `mimetypes` module in isolation), all four icons return 200, and the meta
  tags render correctly in the actual page HTML.

## 5. What was deliberately left out — no service worker

A full "installable" PWA on Android (the native install prompt, not just a
bookmark shortcut) technically wants a registered service worker with a fetch
handler. It was **not** added in this pass, for a concrete reason: Veridact's
phone-testing setup (decisions/0005) generates a **fresh self-signed TLS
certificate on every server restart** (`ssl_context="adhoc"`). Service workers
and certificate changes on the same self-signed origin is a combination this
project has no way to test properly — no real second device to reproduce
"does re-registration behave correctly after the cert rotates," and a broken
service worker (stale cached JS after an update) is a well-known, genuinely
hard-to-debug class of bug. Shipping the manifest and icons alone already
delivers the "installs to the home screen, opens full-screen" outcome that was
actually asked for; the stricter "full native install prompt" polish is
correctly deferred until there's a stable HTTPS origin (a real certificate,
not a fresh ad-hoc one per run) to test it against.

## Trade-off

Without a service worker, Android's install experience today is closer to "add
a shortcut" than the full native install-prompt flow; iOS's "Add to Home
Screen" is unaffected by this (it never required a service worker). Both still
deliver the core outcome — a home-screen icon that opens full-screen with no
browser address bar.
