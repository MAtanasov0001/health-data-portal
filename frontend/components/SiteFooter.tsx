import Link from "next/link";

import type { Locale } from "@/i18n-config";
import type { Dictionary } from "@/lib/dictionaries";

export default function SiteFooter({ lang, dict }: { lang: Locale; dict: Dictionary }) {
  return (
    <footer className="site">
      <div className="container footer-grid">
        <div className="footer-brand">
          <span className="brand-word">{dict.site.brand}</span>
          <p className="footer-tagline">{dict.footer.tagline}</p>
        </div>

        <nav className="footer-col" aria-label={dict.footer.sections.browse}>
          <h2>{dict.footer.sections.browse}</h2>
          <ul>
            <li>
              <Link href={`/${lang}/naborite`}>{dict.nav.datasets}</Link>
            </li>
          </ul>
        </nav>

        <nav className="footer-col" aria-label={dict.footer.sections.developers}>
          <h2>{dict.footer.sections.developers}</h2>
          <ul>
            <li>
              <Link href={`/${lang}/dokumentacia`}>{dict.nav.docs}</Link>
            </li>
            <li>
              <a href="https://git.egov.bg" rel="noopener">
                {dict.footer.repo}
              </a>
            </li>
          </ul>
        </nav>

        <nav className="footer-col" aria-label={dict.footer.sections.about}>
          <h2>{dict.footer.sections.about}</h2>
          <ul>
            <li>
              <Link href={`/${lang}/za-portala`}>{dict.nav.about}</Link>
            </li>
            <li>
              <Link href={`/${lang}/kontakti`}>{dict.nav.contact}</Link>
            </li>
          </ul>
        </nav>
      </div>

      <div className="container footer-legal">
        <p style={{ margin: "0 0 0.35rem" }}>{dict.footer.license}</p>
        <p style={{ margin: 0 }}>
          © {new Date().getFullYear()} {dict.site.publisher}
        </p>
      </div>
    </footer>
  );
}
