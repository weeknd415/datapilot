import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "DataPilot - AI Business Intelligence",
  description:
    "Multi-agent BI system with Text-to-SQL, Document AI, and LangGraph orchestration",
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
