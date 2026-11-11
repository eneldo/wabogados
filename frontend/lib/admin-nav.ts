/**
 * The administration menu.
 *
 * One list, three states, and the state is the point:
 *
 * - `ready`   — the module exists in the backend and has an interface here.
 * - `building`— the module exists in the backend; its screens are not written
 *               yet. It is a link, because the module is real, and the page it
 *               opens says exactly what is missing.
 * - `planned` — `MASTER_PROMPT.md` lists it under "Fases futuras, NO implementar
 *               aún". It is **not a link**. A greyed-out item that goes nowhere
 *               is a dead end; a greyed-out item with a reason is a roadmap.
 *
 * The three `planned` entries are CRM-adjacent: Centro multimedia, Inteligencia
 * Artificial jurídica and Facturación. They are here because the firm asked to
 * see them, and they are inert because the project's own brief forbids building
 * them yet.
 */

export type AdminModuleState = "ready" | "building" | "planned";

export type AdminModule = {
  slug: string;
  label: string;
  /** Where the item goes. `planned` items carry a slug, not an href. */
  href?: string;
  icon: IconName;
  state: AdminModuleState;
  /** Permission required to see the module at all. */
  permission?: string;
  /** Shown on the item when it is not usable. */
  note?: string;
  /**
   * What the roadmap says this module will be, for a `planned` entry.
   *
   * A menu item that only says "not yet" is a dead end for the people who
   * decide: the director reading it learns nothing about what was chosen and
   * when. Naming the phase and the scope costs one string and turns the same
   * inert item into a roadmap they can read.
   */
  future?: { phase: string; scope: string };
};

export type IconName =
  | "dashboard"
  | "cases"
  | "clients"
  | "lawyers"
  | "agenda"
  | "messages"
  | "consultations"
  | "documents"
  | "multimedia"
  | "ai"
  | "billing"
  | "analytics"
  | "security"
  | "config";

export const ADMIN_MODULES: AdminModule[] = [
  {
    slug: "dashboard",
    label: "Dashboard",
    href: "/admin",
    icon: "dashboard",
    state: "ready",
  },
  {
    slug: "expedientes",
    label: "Expedientes",
    href: "/admin/expedientes",
    icon: "cases",
    state: "ready",
    // No gate: expedientes is authorised by scope, not by one permission.
    // The API accepts `cases:read_all`, `cases:read_assigned` and
    // `cases:read_published` and returns only what the profile may see, so a
    // single `cases:read` string here would hide the module from everyone.
  },
  {
    slug: "clientes",
    label: "Clientes",
    href: "/admin/clientes",
    icon: "clients",
    state: "ready",
    permission: "clients:read",
  },
  {
    slug: "abogados",
    label: "Abogados",
    href: "/admin/abogados",
    icon: "lawyers",
    state: "ready",
    permission: "lawyers:read",
  },
  {
    slug: "agenda",
    label: "Agenda",
    href: "/admin/agenda",
    icon: "agenda",
    state: "ready",
    permission: "calendar:read",
  },
  {
    slug: "mensajes",
    label: "Mensajes",
    href: "/admin/mensajes",
    icon: "messages",
    state: "ready",
    permission: "messages:read",
  },
  {
    slug: "notificaciones",
    label: "Notificaciones",
    href: "/admin/notificaciones",
    icon: "messages",
    state: "ready",
    permission: "notifications:read",
  },
  {
    slug: "solicitudes",
    label: "Solicitudes",
    href: "/admin/solicitudes",
    icon: "consultations",
    state: "ready",
    permission: "consultations:read",
  },
  {
    slug: "documentos",
    label: "Documentos",
    href: "/admin/documentos",
    icon: "documents",
    state: "ready",
    // Gated, unlike expedientes: the browser reads across cases, so it needs
    // the document read permission rather than the case scope alone.
    permission: "documents:read",
  },
  {
    slug: "analisis",
    label: "Análisis jurídicos",
    href: "/admin/analisis",
    icon: "documents",
    state: "ready",
    permission: "analyses:read",
  },
  {
    slug: "multimedia",
    label: "Multimedial",
    href: "/admin/multimedia",
    icon: "multimedia",
    state: "ready",
    // Gated on `media:read`. The library is firm material and the client role
    // holds nothing on it, so this one permission really does mean "may open the
    // module" — unlike expedientes, which is authorised by scope.
    permission: "media:read",
  },
  {
    slug: "ia-juridica",
    label: "IA Jurídica",
    href: "/admin/ia-juridica",
    icon: "ai",
    state: "ready",
    // Search and summarisation are two permissions because they are two abilities:
    // a profile allowed to find a document need not be allowed to read it back.
    permission: "ai:search",
  },
  {
    slug: "facturacion",
    label: "Facturación",
    href: "/admin/facturacion",
    icon: "billing",
    state: "ready",
    // Reading and drafting are staff work; issuing and voiding sit behind their own
    // permissions, and the screen only offers them to whoever holds them.
    permission: "invoices:read",
  },
  {
    slug: "seguridad",
    label: "Seguridad",
    href: "/admin/seguridad",
    icon: "security",
    state: "ready",
    // Gated on the directory rather than on the module as a whole: the audit
    // trail and the role catalogue have their own permissions, and the screen
    // shows whichever of the three the profile is allowed to open.
    permission: "users:read",
  },
  {
    slug: "estadisticas-web",
    label: "Estadísticas web",
    href: "/admin/estadisticas-web",
    icon: "analytics",
    state: "ready",
    permission: "website_analytics:read",
  },
  {
    slug: "config",
    label: "Configuración",
    href: "/admin/configuracion",
    icon: "config",
    state: "ready",
    // `settings:read` and `settings:write` are separate: the screen shows the
    // values to anyone who may read them and offers the buttons only to whoever
    // may change them.
    permission: "settings:read",
  },
];

/** Modules a signed-in profile may actually open, in menu order. */
export function visibleModules(permissions: string[]): AdminModule[] {
  return ADMIN_MODULES.filter((module) => {
    if (module.state === "planned") return true;
    if (!module.permission) return true;
    return permissions.includes(module.permission);
  });
}

export function findModule(slug: string): AdminModule | undefined {
  return ADMIN_MODULES.find((module) => module.slug === slug);
}
