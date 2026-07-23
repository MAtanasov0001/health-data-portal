import type { MetadataRoute } from "next";

import { i18n } from "@/i18n-config";
import { listCollections, listDatasets } from "@/lib/api";
import { SITE_URL } from "@/lib/site";

export const dynamic = "force-static";

// Пътища без езиковия префикс — добавя се за всеки локал, с hreflang alternates между тях.
const STATIC_PATHS = ["", "/naborite", "/za-portala", "/dokumentacia", "/kontakti"];

function entry(path: string): MetadataRoute.Sitemap[number] {
  const languages: Record<string, string> = {};
  for (const lang of i18n.locales) languages[lang] = `${SITE_URL}/${lang}${path}`;
  return {
    url: `${SITE_URL}/${i18n.defaultLocale}${path}`,
    changeFrequency: "weekly",
    alternates: { languages },
  };
}

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const paths = [...STATIC_PATHS];
  try {
    const [datasets, collections] = await Promise.all([listDatasets(1, 100), listCollections()]);
    for (const ds of datasets.items) {
      if (!ds.collection) paths.push(`/naborite/${ds.identifier}`);
    }
    for (const c of collections.items) paths.push(`/naborite/kolekciya/${c.id}`);
  } catch {
    // API-то може да е недостъпно при билд — оставаме само със статичните пътища.
  }
  return paths.map(entry);
}
