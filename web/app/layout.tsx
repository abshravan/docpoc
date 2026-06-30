import type { Metadata } from "next";
import "./globals.css";
import { AppShell } from "@/components/app-shell";

export const metadata: Metadata = {
  title: "EPL-CDS — early pregnancy loss decision support",
  description: "Research decision-support tool. LLM extracts facts; a deterministic engine decides.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className="h-full">
      <body
        className="min-h-full"
        style={{
          fontFamily:
            "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
        }}
      >
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
