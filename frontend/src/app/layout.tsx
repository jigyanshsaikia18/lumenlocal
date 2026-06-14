import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "LumenLocal",
  description: "GEO-native multi-tenant GBP optimization for agencies",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
