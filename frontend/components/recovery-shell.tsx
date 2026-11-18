import Link from "next/link";

import { BrandLogo } from "@/components/brand-logo";

export function RecoveryShell({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <main className="flex min-h-screen items-center justify-center px-5 py-12">
      <section className="w-full max-w-md rounded-card border border-rule-strong bg-surface p-6 sm:p-8">
        <Link href="/" aria-label="WABOGADOS, web pública"><BrandLogo size="header" priority /></Link>
        <p className="label-rule mt-8">Recuperación de acceso</p>
        <h1 className="font-display mt-2 text-3xl">{title}</h1>
        <div className="mt-5">{children}</div>
        <p className="mt-6 text-xs leading-relaxed text-ink-muted">Si ya no tiene acceso a su correo, contacte al administrador para verificar su identidad.</p>
        <Link href="/login" className="mt-6 inline-block text-sm text-ink-soft underline underline-offset-4">Volver a iniciar sesión</Link>
      </section>
    </main>
  );
}
