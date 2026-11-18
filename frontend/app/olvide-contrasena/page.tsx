import type { Metadata } from "next";

import { ForgotPasswordForm } from "@/components/password-recovery-form";
import { RecoveryShell } from "@/components/recovery-shell";
import { recoveryAvailable } from "@/lib/password-recovery-server";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Olvidé mi contraseña | WABOGADOS", robots: { index: false, follow: false }, referrer: "no-referrer" };

export default async function ForgotPasswordPage() {
  return <RecoveryShell title="Olvidé mi contraseña"><ForgotPasswordForm enabled={await recoveryAvailable()} /></RecoveryShell>;
}
