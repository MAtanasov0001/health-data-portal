import type { Metadata } from "next";

import { i18n } from "@/i18n-config";

// Каноничен публичен адрес на портала — за metadataBase, sitemap, robots и hreflang.
// Може да се пренастрои при внедряване (git.egov.bg / ДХЧО) чрез NEXT_PUBLIC_SITE_URL.
export const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL ?? "https://data.health.egov.bg").replace(
  /\/$/,
  "",
);

/** hreflang + canonical за конкретен път (без езиков префикс, напр. ``/naborite``). */
export function alternates(lang: string, path = ""): NonNullable<Metadata["alternates"]> {
  return {
    canonical: `/${lang}${path}`,
    languages: Object.fromEntries(i18n.locales.map((l) => [l, `/${l}${path}`])),
  };
}
