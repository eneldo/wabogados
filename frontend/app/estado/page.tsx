import Link from "next/link";
import { BrandLogo } from "@/components/brand-logo";

type ApiHealth = {
  status: "ok" | "ready";
  service: string;
  checks: Record<string, "up">;
};

type ServiceStatus = {
  available: boolean;
  label: string;
  detail: string;
};

async function getApiStatus(): Promise<ServiceStatus> {
  const apiUrl = process.env.API_INTERNAL_URL ?? "http://localhost:8000";

  try {
    const response = await fetch(`${apiUrl}/api/v1/health/ready`, {
      cache: "no-store",
      signal: AbortSignal.timeout(3000),
    });
    if (!response.ok) {
      return { available: false, label: "No disponible", detail: "La API no está preparada." };
    }
    const health = (await response.json()) as ApiHealth;
    return {
      available: health.status === "ready",
      label: health.status === "ready" ? "Operativo" : "No disponible",
      detail: `Servicio ${health.service}; base de datos ${health.checks.database ?? "desconocida"}.`,
    };
  } catch {
    return { available: false, label: "No disponible", detail: "No fue posible contactar la API." };
  }
}

export default async function StatusPage() {
  const api = await getApiStatus();

  return (
    <main className="mx-auto flex min-h-screen max-w-4xl items-center px-6 py-16">
      <section aria-labelledby="status-title" className="w-full rounded-card border border-rule bg-surface p-8 shadow-card sm:p-12">
        <Link href="/" aria-label="WABOGADOS, web pública"><BrandLogo size="sidebar" priority /></Link>
        <p className="mt-6 mb-3 text-sm font-semibold uppercase tracking-[0.2em] text-wax">WABOGADOS V1</p>
        <h1 id="status-title" className="text-4xl font-bold tracking-tight sm:text-5xl">Estado del sistema</h1>
        <p className="mt-4 max-w-2xl text-lg text-ink-muted">Disponibilidad actual de los servicios base de la plataforma.</p>
        <div className="mt-10 rounded-card border border-rule p-6">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <h2 className="text-xl font-semibold">API y base de datos</h2>
            <span role="status" aria-live="polite" className={`rounded-full px-4 py-2 text-sm font-bold ${api.available ? "bg-forest-tint text-forest" : "bg-wax-tint text-wax-deep"}`}>
              <span aria-hidden="true">● </span>{api.label}
            </span>
          </div>
          <p className="mt-4 text-ink-muted">{api.detail}</p>
        </div>
      </section>
    </main>
  );
}
