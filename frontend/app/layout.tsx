import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "ProofPay AI · Evidence Room", template: "%s · ProofPay AI" },
  description: "A traceable evidence room for payment disputes. Every finding has a source, and every response stays in your hands.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
