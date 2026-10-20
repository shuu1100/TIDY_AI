import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "TidyAI — Local Desktop File Organizer",
  description:
    "Organize, deduplicate, and tidy your local directories safely with local AI and zero cloud telemetry.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={inter.className}>
      <body className="bg-[#fbf9f3] text-[#1b1c18] antialiased min-h-screen selection:bg-[#e5b94f]/25 selection:text-[#1b1c18]">
        {children}
      </body>
    </html>
  );
}
