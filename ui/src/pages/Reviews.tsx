const rounds = [
  { n: 1, href: "/reviews/round-1.html", live: true },
  { n: 2, href: "/reviews/round-2.html", live: true },
  { n: 3, href: "/reviews/round-3.html", live: false },
];

export function Reviews() {
  return (
    <div className="stack">
      <div>
        <h1 className="h1">Reviews</h1>
        <p className="text-muted" style={{ marginTop: "0.25rem" }}>
          Society-of-Agents reviews each published paper after every round. Open a round below to see the full compiled report.
        </p>
      </div>

      <div className="stack" style={{ gap: "0.75rem" }}>
        {rounds.map((r) => (
          <a
            key={r.n}
            href={r.href}
            target="_blank"
            rel="noreferrer"
            className="card"
            style={{
              display: "block",
              padding: "1rem 1.25rem",
              textDecoration: "none",
              color: "inherit",
            }}
          >
            <div className="row" style={{ justifyContent: "space-between" }}>
              <div className="row" style={{ gap: "0.5rem" }}>
                <span style={{ fontWeight: 600 }}>Round {r.n}</span>
                {r.live && <span className="pill">Live</span>}
              </div>
              <span className="text-faint">↗</span>
            </div>
          </a>
        ))}
      </div>
    </div>
  );
}
