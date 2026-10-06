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

export function landingFor(
  roles: readonly string[],
  permissions: readonly string[],
): Landing {
  const isClient =
    roles.includes("cliente") && !roles.some((role) => role !== "cliente");

  if (isClient) return { href: "/portal", label: "Portal del cliente" };

  // Staff with a wide read sees the whole case book; everyone else sees the
  // cases they are assigned to. Both are the same surface, scoped differently.
  if (permissions.includes("cases:read_all")) {
    return { href: "/expedientes", label: "Expedientes" };
  }
  return { href: "/expedientes", label: "Mis expedientes" };
}
