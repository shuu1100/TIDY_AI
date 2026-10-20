import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "TidyAI — Privacy-First File Organization Assistant",
  description:
    "Organize, deduplicate, and tidy your local directories safely with local AI and zero cloud telemetry.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-neutral-950 text-neutral-100 antialiased font-sans">
        {children}
      </body>
    </html>
  );
}
