import type { Dictionary } from "@/lib/dictionaries";

export default function SiteFooter({ dict }: { dict: Dictionary }) {
  return (
    <footer className="site">
      <div className="container">
        <p style={{ margin: "0 0 0.5rem" }}>{dict.footer.license}</p>
        <p style={{ margin: 0 }}>
          © {new Date().getFullYear()} {dict.site.publisher} ·{" "}
          <a href="https://git.egov.bg" rel="noopener">
            {dict.footer.repo}
          </a>
        </p>
      </div>
    </footer>
  );
}
