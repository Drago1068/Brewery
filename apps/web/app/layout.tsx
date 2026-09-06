import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import "./globals.css";

export const metadata: Metadata = {
  title: "Brewing Platform",
  description: "Measured brewing, repeatable results.",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <header className="site-header">
          <Link className="brand" href="/" aria-label="Brewing Platform home">
            <span className="brand-mark" aria-hidden="true">BP</span>
            <span>Brewing Platform</span>
          </Link>
          <nav aria-label="Primary navigation">
            <Link href="/">Recipes</Link>
            <Link href="/designer">Recipe Designer</Link>
            <Link href="/#active-brew">Active brew</Link>
            <Link href="/#active-fermentation">Active fermentation</Link>
          </nav>
        </header>
        <main>{children}</main>
        <footer>Phase 4 · Private brewing workspace · Deterministic calculations</footer>
      </body>
    </html>
  );
}
