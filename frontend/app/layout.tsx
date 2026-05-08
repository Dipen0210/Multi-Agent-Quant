import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "QuantSentiment — Multi-Agent Financial Analysis",
  description: "6-agent AI system for financial reasoning: News, Technical, Macro, Risk, Portfolio, Critic",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
