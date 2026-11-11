export type WebsiteCounts = {
  page_views: number;
  estimated_visitors: number;
  phone_clicks: number;
  consultations: number;
};

export type WebsitePage = { path: string; page_views: number; phone_clicks: number };

export type WebsiteSummary = {
  start: string;
  end: string;
  timezone: string;
  generated_at: string;
  totals: WebsiteCounts;
  daily: (WebsiteCounts & { day: string })[];
  monthly: (WebsiteCounts & { month: string })[];
  pages: WebsitePage[];
  areas: WebsitePage[];
};
