import type { Metadata } from "next";

import { ResetPasswordForm } from "@/components/password-recovery-form";
import { RecoveryShell } from "@/components/recovery-shell";
import { recoveryAvailable } from "@/lib/password-recovery-server";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Restablecer contraseña | WABOGADOS", robots: { index: false, follow: false }, referrer: "no-referrer" };

export default async function ResetPasswordPage() {
  return <RecoveryShell title="Nueva contraseña"><ResetPasswordForm enabled={await recoveryAvailable()} /></RecoveryShell>;
}
