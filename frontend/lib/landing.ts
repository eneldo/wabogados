/**
 * Where a signed-in person lands.
 *
 * The public site promises a portal for each role, so the login has to honour
 * that: a client belongs on their file, and someone who works in the firm
 * belongs on the case book. Sending everyone to the same page would make the
 * promise on the landing page untrue.
 *
 * The decision is made from the permissions the server already returned, not
 * from a role name, so a custom role lands somewhere sensible instead of
 * nowhere.
 */

export type Landing = {
  href: string;
  label: string;
};

export function isClientOnly(roles: readonly string[]): boolean {
  return roles.includes("cliente") && roles.every((role) => role === "cliente");
}

export function landingFor(
  roles: readonly string[],
  permissions: readonly string[],
): Landing {
  if (isClientOnly(roles)) return { href: "/portal", label: "Portal del cliente" };

  // Administrator always goes to the administration dashboard.
  if (roles.includes("administrador")) {
    return { href: "/admin", label: "Panel de administración" };
  }

  // Staff with a wide read sees the whole case book; everyone else sees the
  // cases they are assigned to. Both are the same surface, scoped differently.
  if (permissions.includes("cases:read_all")) {
    return { href: "/expedientes", label: "Expedientes" };
  }
  return { href: "/expedientes", label: "Mis expedientes" };
}
