import { AnalysisManager } from "@/components/admin/analisis/analysis-manager";
import { apiFetch } from "@/lib/api";

type Analysis = {
  id: string;
  title: string;
  slug: string;
  summary: string | null;
  content: string;
  author_name: string | null;
  is_published: boolean;
  published_at: string | null;
  is_active: boolean;
};

export default async function AnalisisAdminPage() {
  const items = await apiFetch<Analysis[]>("/api/v1/analyses", {
    query: { include_inactive: true },
  }).catch(() => [] as Analysis[]);

  return (
    <div className="space-y-6">
      <h1 className="font-display text-2xl">Análisis jurídicos</h1>
      <AnalysisManager initial={items} />
    </div>
  );
}