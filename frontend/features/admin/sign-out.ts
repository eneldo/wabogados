"use server";

import { redirect } from "next/navigation";

import { clearSession, revokeSession } from "@/lib/session";

/**
 * Sign out.
 *
 * A server action rather than a form pointed at `/api/session`, for two reasons.
 * The route handler answers JSON, and a plain `<form method="post">` would land
 * the person on a raw `{"ok":true}`; and clearing the cookies is a write, which
 * only a server action can do from a rendered page.
 *
 * **The session is revoked server side before the cookies go.** This used to
 * only drop the cookies, and the note then claimed the alternative was a
 * `beforeunload` call that browsers cancel — which is not why it was hard: a
 * server action is a request the server awaits before redirecting, so there is
 * nothing for the browser to cancel. Leaving the refresh token alive meant a
 * signed-out session kept working for up to seven days.
 *
 * Revocation never blocks the sign-out; if the API is unreachable the cookies
 * are cleared anyway and the token expires on its own.
 */
export async function signOut(): Promise<void> {
  await revokeSession();
  await clearSession();
  redirect("/login");
}
