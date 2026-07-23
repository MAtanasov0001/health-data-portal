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
        <Link className="brand" href={`/${lang}`} aria-label={dict.site.name}>
          {/* Място за логото — заменя се с истинското лого, щом бъде качено. */}
          <span className="brand-mark" aria-hidden="true">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path
                d="M12 3v18M3 12h18"
                stroke="currentColor"
                strokeWidth="2.5"
                strokeLinecap="round"
              />
            </svg>
          </span>
          <span className="brand-text">
            <span className="brand-word">{dict.site.brand}</span>
            <span className="brand-sub">{dict.site.name}</span>
          </span>
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
