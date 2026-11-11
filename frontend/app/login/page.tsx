import Link from "next/link";
import { redirect } from "next/navigation";

import { LoginForm } from "@/components/login-form";
import { BrandLogo } from "@/components/brand-logo";
import { ServiceUnavailable } from "@/components/service-unavailable";
import { landingFor } from "@/lib/landing";
import { requireSession } from "@/lib/session-guard";

export default async function LoginPage() {
  // Verify the cookie through the same internal API and guard as the portal.
  // Invalid sessions show the form; outages are not redirects or empty profiles.
  const session = await requireSession();
  if (session.kind === "ok") {
    redirect(landingFor(session.profile.roles, session.profile.permissions).href);
  }
  if (session.kind === "unavailable") {
    return (
      <ServiceUnavailable
        message="No fue posible verificar su sesión. Vuelva a intentarlo en unos momentos."
        backHref="/login"
        backLabel="Reintentar acceso"
      />
    );
  }

  return (
    <main className="grid min-h-screen lg:grid-cols-[1.1fr_1fr]">
      {/* The left panel states what this is. A login screen that only says
          "login" asks a non-technical client to trust something they have no
          way to evaluate. */}
      <section className="relative hidden flex-col justify-between border-r border-rule-strong bg-surface px-12 py-14 lg:flex overflow-hidden">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_30%_20%,rgba(237,28,36,0.12),transparent_60%)]" />
        <Link href="/" className="flex items-center gap-3">
          <BrandLogo size="login" priority />
        </Link>

        <div className="max-w-md">
          <h1 className="font-display text-[2.75rem] leading-[1.1] text-ink">
            Su espacio jurídico,
            <br />
            <span className="text-wax">conectado</span> con la firma.
          </h1>
          <p className="mt-5 text-[0.95rem] leading-relaxed text-ink-soft">
            Clientes, abogados y equipo administrativo comparten una misma
            plataforma. Cada persona accede a la información y herramientas
            habilitadas para su perfil.
          </p>

          <ul className="mt-9 space-y-3.5">
            {[
              "Clientes: seguimiento de procesos y comunicación con su abogado",
              "Abogados y personal: expedientes y herramientas de trabajo",
              "Administración: gestión integral de la plataforma",
            ].map((item) => (
              <li key={item} className="flex gap-3 text-sm text-ink-soft">
                <span aria-hidden="true" className="mt-2 size-1 shrink-0 rounded-full bg-wax" />
                {item}
              </li>
            ))}
          </ul>
        </div>

        <p className="text-xs leading-relaxed text-ink-faint">
          Acceso restringido. El acceso queda registrado.
        </p>
      </section>

      <section className="flex items-center justify-center px-6 py-16">
        <div className="w-full max-w-sm">
          <div className="mb-8 lg:hidden">
            <Link href="/" aria-label="WABOGADOS, web pública">
              <BrandLogo size="header" priority />
            </Link>
          </div>
          <p className="label-rule">Acceso</p>
          <h2 className="font-display mt-1 mb-7 text-3xl">Iniciar sesión</h2>
          <LoginForm />
          <Link
            href="/"
            className="mt-8 block text-center text-xs text-ink-muted underline-offset-4 hover:text-wax hover:underline"
          >
            Volver a la web pública
          </Link>
        </div>
      </section>
    </main>
  );
}
