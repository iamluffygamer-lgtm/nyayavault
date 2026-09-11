import type { Metadata, Viewport } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "NyayaVault — Secure Legal & Investigation Document Management",
  description:
    "Case-centric document and evidence management with SHA-256 integrity verification and a hash-linked audit trail.",
  robots: { index: false, follow: false },
};

export const viewport: Viewport = {
  themeColor: "#ffffff",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="app-ground min-h-screen antialiased">{children}</body>
    </html>
  );
}
