import type { ReactNode } from "react";

import "./globals.css";
import { ClientProviders } from "./ClientProviders";

export const metadata = {
  title: "ZT-ATE Sentinel Node",
  description: "Zero-Trust Autonomous Talent Ecosystem"
};

export default function RootLayout({
  children
}: Readonly<{
  children: ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className="h-screen overflow-hidden bg-[#0a0a0a] text-slate-100 flex flex-col"
        suppressHydrationWarning
      >
        <ClientProviders>{children}</ClientProviders>
      </body>
    </html>
  );
}
