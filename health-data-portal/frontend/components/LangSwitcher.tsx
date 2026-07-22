"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { i18n, type Locale } from "@/i18n-config";

// Превключва езика, като запазва текущия път (сменя само първия сегмент).
export default function LangSwitcher({ current, label }: { current: Locale; label: string }) {
  const pathname = usePathname() || `/${current}`;
  const rest = pathname.replace(new RegExp(`^/(${i18n.locales.join("|")})`), "") || "";

  return (
    <div className="langswitch">
      <span aria-hidden="true">{label}:</span>
      <ul style={{ display: "flex", gap: "0.5rem", listStyle: "none", margin: 0, padding: 0 }}>
        {i18n.locales.map((loc) => (
          <li key={loc}>
            <Link
              href={`/${loc}${rest}`}
              hrefLang={loc}
              aria-current={loc === current ? "true" : undefined}
              lang={loc}
            >
              {loc.toUpperCase()}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
