import type { Metadata } from "next";
import { Fraunces, IBM_Plex_Mono, IBM_Plex_Sans } from "next/font/google";

import "./globals.css";
import "./public-site.css";

import { WebVitals } from "@/components/web-vitals";

/*
  Three faces, each with a job. Fraunces carries the voice of the document.
  IBM Plex Sans is the interface: institutional, designed for German technical
  standards, and it holds up in Spanish. Plex Mono is for anything a person
  might have to read character by character — a hash, a case number, a byte
  count — where a proportional face would be a liability.
*/
const fraunces = Fraunces({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-fraunces",
  axes: ["SOFT", "WONK", "opsz"],
});

const plexSans = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  display: "swap",
  variable: "--font-plex-sans",
});

const plexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  display: "swap",
  variable: "--font-plex-mono",
});

export const metadata: Metadata = {
  title: "WABOGADOS V1",
  description: "Gestión de expedientes, evidencias y comunicación con el despacho.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="es"
      className={`${fraunces.variable} ${plexSans.variable} ${plexMono.variable}`}
    >
      <body>
        {/*
          Marks the document as script-capable, before anything below it renders.

          The scroll-reveal stylesheet hides elements below the fold only when
          this class is present. With scripts blocked the class is never added,
          so nothing is ever invisible — the page simply has no animation, which
          is the correct degradation for a law firm's public site.

          A real `<script>` element, not `dangerouslySetInnerHTML` on `<html>`:
          that prop sets the element's *children*, and putting it on the root
          element would replace the document rather than mark it.
        */}
        <script
          dangerouslySetInnerHTML={{
            __html: "document.documentElement.classList.add('js')",
          }}
        />
        <WebVitals />
        {children}
      </body>
    </html>
  );
}