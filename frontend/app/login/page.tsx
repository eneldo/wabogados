import Link from "next/link";
import { redirect } from "next/navigation";

import { LoginForm } from "@/components/login-form";
import { readAccessToken } from "@/lib/session";
export default async function LoginPage() {
  // A session that already exists should not see the form again.
  if (await readAccessToken()) redirect("/portal");

  return (
    <main className="grid min-h-screen lg:grid-cols-[1.1fr_1fr]">
      {/* The left panel states what this is. A login screen that only says
          "login" asks a non-technical client to trust something they have no
          way to evaluate. */}
      <section className="relative hidden flex-col justify-between border-r border-rule-strong bg-surface px-12 py-14 lg:flex">
        <Link href="/" className="flex items-center gap-3">
          <span className="brand-word">
            <em>W</em>ABOGADOS
            <small>ESTRATEGIA JURÍDICA</small>
          </span>
        </Link>

        <div className="max-w-md">
          <h1 className="font-display text-[2.75rem] leading-[1.1] text-ink">
            Su expediente,
            <br />
            <span className="text-wax">al día</span>, siempre que lo necesite.
          </h1>
          <p className="mt-5 text-[0.95rem] leading-relaxed text-ink-soft">
            Consulte el estado de sus procesos, los documentos que el despacho
            ha puesto a su disposición y converse con su abogado sin
            intermediarios.
          </p>

          <ul className="mt-9 space-y-3.5">
            {[
              "El estado de cada proceso, con su última actuación",
              "Documentos y evidencias que el despacho le ha publicado",
              "Mensajes directos con su abogado",
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
            <Link href="/" className="brand-word">
              <em>W</em>ABOGADOS
              <small>ESTRATEGIA JURÍDICA</small>
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
