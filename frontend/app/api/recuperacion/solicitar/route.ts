import { forwardRecovery } from "@/lib/password-recovery-server";

export async function POST(request: Request) {
  return forwardRecovery(request, "forgot");
}
