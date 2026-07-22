import type { Metadata } from "next";

import { API_BASE } from "@/lib/api";
import { i18n, isLocale, type Locale } from "@/i18n-config";
import { getDictionary } from "@/lib/dictionaries";

export const metadata: Metadata = { title: "Техническа документация" };

export default function DocsPage({ params }: { params: { lang: string } }) {
  const lang: Locale = isLocale(params.lang) ? params.lang : i18n.defaultLocale;
  const dict = getDictionary(lang);

  return (
    <>
      <h1>{dict.docs.title}</h1>
      <p className="lead">{dict.docs.lead}</p>

      <h2>API</h2>
      <ul>
        <li>
          <a href={`${API_BASE}/docs`}>OpenAPI / Swagger UI</a>
        </li>
        <li>
          <a href={`${API_BASE}/openapi.json`}>openapi.json (3.1)</a>
        </li>
        <li>
          <a href={`${API_BASE}/v1/catalog.jsonld`}>DCAT-AP каталог (JSON-LD)</a>
        </li>
      </ul>

      <h2>Примери</h2>
      <pre>
        <code>{`# Списък с набори (пагиниран)
curl "${API_BASE}/v1/datasets?page=1&page_size=20"

# Детайл на набор
curl "${API_BASE}/v1/datasets/hospitalizacii-po-oblast-2023"

# Данни (CSV / JSON)
curl "${API_BASE}/v1/datasets/hospitalizacii-po-oblast-2023/data.csv"
curl "${API_BASE}/v1/datasets/hospitalizacii-po-oblast-2023/data.json"

# CKAN-съвместимо харвестване
curl "${API_BASE}/api/3/action/package_list"`}</code>
      </pre>
    </>
  );
}
