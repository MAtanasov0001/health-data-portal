// Клиент за публичното четящо API. Използва се от сървъра (SSR) при извличане на набори.

export const API_BASE = process.env.OHDP_API_BASE ?? "http://127.0.0.1:8000";

// Каталожно ядро (CKAN, вариант А) — DCAT-AP / CKAN крайни точки за харвестване.
export const CKAN_BASE = process.env.OHDP_CKAN_URL ?? "http://127.0.0.1:5000";

export interface DatasetSummary {
  identifier: string;
  uri: string;
  title: Record<string, string>;
  version: string;
  issued: string;
  row_count: number;
  themes: string[];
}

export interface DatasetList {
  total: number;
  page: number;
  page_size: number;
  items: DatasetSummary[];
}

export interface DatasetDetail extends DatasetSummary {
  checksum_sha256: string;
  dcat: Record<string, unknown>;
  distributions: Record<string, string>;
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    // Кратко кеширане; каталогът е публичен и се обновява рядко.
    next: { revalidate: 60 },
    headers: { Accept: "application/json" },
  });
  if (!res.ok) {
    throw new Error(`API ${path} → ${res.status}`);
  }
  return (await res.json()) as T;
}

export function listDatasets(page = 1, pageSize = 20): Promise<DatasetList> {
  return getJson<DatasetList>(`/v1/datasets?page=${page}&page_size=${pageSize}`);
}

export async function getDataset(identifier: string): Promise<DatasetDetail | null> {
  try {
    return await getJson<DatasetDetail>(`/v1/datasets/${encodeURIComponent(identifier)}`);
  } catch {
    return null;
  }
}

/** Заглавие според езика, с разумно връщане към наличния. */
export function localizedTitle(title: Record<string, string>, locale: string): string {
  return title[locale] ?? title.bg ?? Object.values(title)[0] ?? "";
}
