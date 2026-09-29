import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import AuthGuard from "../components/AuthGuard";
import Header from "../components/Header";

const inter = Inter({ subsets: ["latin"], display: "swap" });

export const metadata: Metadata = {
  title: "TrackFlow Backoffice | Operational Dashboard",
  description: "Internal operations control panel for TrackFlow warehouse and last-mile logistics.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>): React.ReactElement {
  return (
    <html lang="en" className={`${inter.className} h-full antialiased dark`}>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
      </head>
      <body className="min-h-full flex flex-col bg-slate-950 text-slate-100 font-sans selection:bg-cyan-500 selection:text-white">
        <AuthGuard>
          <Header />
          <main className="flex-1 bg-slate-950 text-slate-100">
            {children}
          </main>
        </AuthGuard>
      </body>
    </html>
  );
}
