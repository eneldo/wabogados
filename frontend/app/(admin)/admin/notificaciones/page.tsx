import { Button } from "@/components/admin/form-controls";
import { PageHeader } from "@/components/admin/page-furniture";
import { Card, EmptyState } from "@/components/primitives";
import { ServiceUnavailable } from "@/components/service-unavailable";
import { apiFetch } from "@/lib/api";
import { requireSession } from "@/lib/session-guard";

type Notification = {
  id: string;
  notification_type: string;
  title: string;
  body: string | null;
  is_read: boolean;
  created_at: string;
};

export default async function NotificacionesPage() {
  const session = await requireSession();
  if (session.kind === "unauthenticated") {
    const { redirect } = await import("next/navigation");
    redirect("/login");
  }
  if (session.kind === "unavailable") {
    return <ServiceUnavailable message={session.message} backHref="/admin" />;
  }

  let items: Notification[] = [];
  try {
    items = await apiFetch<Notification[]>("/api/v1/notifications");
  } catch {
    items = [];
  }

  return (
    <div>
      <PageHeader
        eyebrow="Comunicación"
        title="Notificaciones"
        description="Plazos y avisos del estudio. Sincroniza los vencimientos próximos para generar avisos."
      />
      <form action="/api/proxy/api/v1/notifications/sync-deadlines" method="post" className="mt-4">
        <Button type="submit">Sincronizar plazos (7 días)</Button>
      </form>
      <div className="mt-6 space-y-3">
        {items.length === 0 ? (
          <EmptyState title="Sin notificaciones" hint="Sincroniza los plazos para generar avisos." />
        ) : (
          items.map((n) => (
            <Card key={n.id}>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="font-medium text-ink">{n.title}</p>
                  {n.body ? <p className="mt-1 text-sm text-ink-muted">{n.body}</p> : null}
                  <p className="mt-1 text-xs text-ink-faint">
                    {new Date(n.created_at).toLocaleString("es-CO")}
                  </p>
                </div>
                <span className={`text-xs ${n.is_read ? "text-ink-faint" : "text-wax"}`}>
                  {n.is_read ? "Leída" : "Nueva"}
                </span>
              </div>
            </Card>
          ))
        )}
      </div>
    </div>
  );
}