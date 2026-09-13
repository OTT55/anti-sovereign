import { fontVariables } from "@anti-sovereign/design-system/fonts";
import type { Metadata, Viewport } from "next";
import "./globals.css";
import { AuthNav } from "./nav";
import { RegisterServiceWorker } from "./register-sw";

export const metadata: Metadata = {
  title: "FrameVault",
  description: "Dailies and asset vault; ecosystem identity and reputation hub",
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
          <AuthNav />
        </header>
        <main className="mx-auto max-w-3xl px-6 py-10">{children}</main>
        <RegisterServiceWorker />
      </body>
    </html>
  );
}
