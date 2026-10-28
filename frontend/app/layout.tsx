import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "QuantSentiment — Research Workspace",
  description: "Evidence-grounded financial research with inspectable sources, uncertainty, and agent traces.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
