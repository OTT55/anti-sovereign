import { fontVariables } from "@anti-sovereign/design-system/fonts";
import type { Metadata, Viewport } from "next";
import Link from "next/link";
import "@anti-sovereign/design-system/editorial.css";
import "./globals.css";
import { LiveRoot } from "./_components/LiveRoot";
import { RegisterServiceWorker } from "./register-sw";

export const metadata: Metadata = {
  title: "Canonlock",
  description: "SHA-256 registry: Merkle inclusion proofs, sealed certificates, RFC-3161 timestamps.",
  manifest: "/manifest.webmanifest",
  icons: [{ rel: "icon", url: "/icon.svg", type: "image/svg+xml" }],
};

export const viewport: Viewport = {
  themeColor: "#0b0b0d",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={fontVariables}>
      <body className="min-h-screen font-sans antialiased">
        <header className="border-b border-border">
          <nav className="mx-auto flex max-w-3xl items-center justify-between px-6 py-4">
            <Link href="/" className="font-display text-lg font-semibold text-text">
              Canon<span className="text-accent">lock</span>
            </Link>
            <div className="flex gap-6 font-mono text-sm text-muted">
              <Link href="/" className="hover:text-text">
                Register
              </Link>
              <Link href="/verify" className="hover:text-text">
                Verify
              </Link>
            </div>
          </nav>
        </header>
        <main>{children}</main>
        <footer className="rule px-6 py-6">
          <div className="mx-auto max-w-data">
            <LiveRoot />
          </div>
        </footer>
        <RegisterServiceWorker />
      </body>
    </html>
  );
}
