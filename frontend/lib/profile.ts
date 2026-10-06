/**
 * Who is signed in.
 *
 * The role names are translated once, here, so a page never has to decide
 * whether to show "administrador" or "Administrador".
 */

import { apiFetchOr, ApiNotAuthenticated } from "@/lib/api";
import { readAccessToken } from "@/lib/session";
import type { SessionProfile, UnreadSummary } from "@/lib/types";

export type Profile = {
  id: string;
  email: string;
  name: string;
  roleLabel: string;
  unread: number;
  permissions: string[];
  isClient: boolean;
  canSeeEvidenceManager: boolean;
};

const ROLE_LABELS: Record<string, string> = {
  administrador: "Administración",
  abogado: "Abogado",
  asistente: "Asistente",
  cliente: "Cliente",
};

type MeResponse = {
  id?: string;
  email?: string;
  full_name?: string;
  roles?: string[];
  permissions?: string[];
};

/**
 * Resolve the current profile.
 *
 * Returns null when there is no session, which is the signal to redirect. The
 * unread badge is optional: a failure there must not stop the page rendering,
 * because a missing counter is not a reason to hide a client's hearing.
 */
export async function getProfile(): Promise<Profile | null> {
  if (!(await readAccessToken())) return null;

  let me: MeResponse;
  try {
    me = await apiFetchOr<MeResponse>({}, "/api/v1/auth/me");
  } catch (error) {
    if (error instanceof ApiNotAuthenticated) return null;
    throw error;
  }

  const roles = me.roles ?? [];
  const permissions = me.permissions ?? [];
  const primary = roles[0] ?? "";

  const unread = await apiFetchOr<UnreadSummary>(
    { unread_messages: 0, unread_notifications: 0 },
    "/api/v1/messages/unread/summary",
  ).then((summary) => summary.unread_messages + summary.unread_notifications);

  return {
    id: me.id ?? "",
    email: me.email ?? "",
    name: me.full_name?.trim() || me.email?.split("@")[0] || "Usuario",
    roleLabel: ROLE_LABELS[primary] ?? primary ?? "",
    unread,
    permissions,
    isClient: primary === "cliente",
    // The evidence manager is staff-only. The permission list is the check, not
    // the role name, so a custom role that may upload still gets in.
    canSeeEvidenceManager: permissions.some((name) =>
      ["evidences:create", "evidences:upload", "evidences:view"].includes(name),
    ),
  };
}

export type { SessionProfile };
