import Link from "next/link";

import LangSwitcher from "@/components/LangSwitcher";
import type { Locale } from "@/i18n-config";
import type { Dictionary } from "@/lib/dictionaries";

export default function SiteHeader({ lang, dict }: { lang: Locale; dict: Dictionary }) {
  const nav = [
    { href: "", label: dict.nav.home },
    { href: "/naborite", label: dict.nav.datasets },
    { href: "/dokumentacia", label: dict.nav.docs },
    { href: "/za-portala", label: dict.nav.about },
    { href: "/kontakti", label: dict.nav.contact },
  ];

  return (
    <header className="site">
      <div className="container bar">
        <Link className="brand" href={`/${lang}`}>
          {dict.site.short}
        </Link>
        <nav className="primary" aria-label={dict.site.name}>
          <ul>
            {nav.map((item) => (
              <li key={item.href}>
                <Link href={`/${lang}${item.href}`}>{item.label}</Link>
              </li>
            ))}
          </ul>
        </nav>
        <LangSwitcher current={lang} label={dict.nav.language} />
      </div>
    </header>
  );
}
