import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../api";
import { useAuth } from "../auth";
import type { PaperSummary } from "../types";

const PAGE_SIZE = 25;

type KindFilter = "all" | "submitted" | "preprint";
type TeamFilter = "all" | "mine";

export function Browse() {
  const { user } = useAuth();
  const [papers, setPapers] = useState<PaperSummary[] | null>(null);
  const [total, setTotal] = useState<number | null>(null);
  const [page, setPage] = useState(0);
  const [kindFilter, setKindFilter] = useState<KindFilter>("all");
  const [teamFilter, setTeamFilter] = useState<TeamFilter>("all");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    api.papers
      .list(PAGE_SIZE, page * PAGE_SIZE, {
        kind: kindFilter === "all" ? undefined : kindFilter,
        teamId:
          teamFilter === "mine" && user?.teamName ? user.teamName : undefined,
      })
      .then(({ data, total }) => {
        setPapers(data);
        setTotal(total);
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [page, kindFilter, teamFilter, user?.teamName]);

  // Reset to page 0 whenever filters change so we don't land past the end.
  useEffect(() => {
    setPage(0);
  }, [kindFilter, teamFilter]);

  const filtersActive = kindFilter !== "all" || teamFilter !== "all";

  if (error) return <p className="error">{error}</p>;
  if (!papers) return <p className="text-muted">Loading papers…</p>;
  // Empty state only when there are truly no papers anywhere — i.e. the user
  // hasn't filtered anything. Filtered empty states get a different message
  // so a misclick doesn't look like "welcome, no papers yet".
  if (papers.length === 0 && page === 0 && !filtersActive) {
    return (
      <div className="stack">
        <h1 className="h1">Papers</h1>
        <div className="card stack">
          <h2 className="h2">Welcome — no papers yet.</h2>
          <p className="text-muted">
            Get your CLI set up and publish your first paper. The full walk-through is on the{" "}
            <Link to="/getting-started" className="text-accent" style={{ fontWeight: 600 }}>
              Getting Started
            </Link>{" "}
            page.
          </p>
          <div className="row">
            <Link to="/getting-started" className="button">
              Read Getting Started
            </Link>
            <Link to="/settings" className="button button-ghost">
              Create an API key
            </Link>
          </div>
        </div>
      </div>
    );
  }

  const start = papers.length === 0 ? 0 : page * PAGE_SIZE + 1;
  const end = page * PAGE_SIZE + papers.length;
  const hasNextPage =
    total !== null ? end < total : papers.length === PAGE_SIZE;
  const totalPages =
    total !== null ? Math.max(1, Math.ceil(total / PAGE_SIZE)) : null;

  return (
    <div>
      <div className="row" style={{ justifyContent: "space-between", alignItems: "baseline" }}>
        <h1 className="h1">Papers</h1>
        <span className="text-faint" style={{ fontSize: "0.875rem" }}>
          {total !== null ? `${start}–${end} of ${total}` : `${start}–${end}`}
        </span>
      </div>
      <div className="row" style={{ marginBottom: "1rem", flexWrap: "wrap", gap: "1.25rem" }}>
        <FilterGroup
          label="Kind"
          value={kindFilter}
          onChange={setKindFilter}
          options={[
            { value: "all", label: "All" },
            { value: "submitted", label: "Submitted" },
            { value: "preprint", label: "Preprints" },
          ]}
        />
        <FilterGroup
          label="Team"
          value={teamFilter}
          onChange={setTeamFilter}
          options={[
            { value: "all", label: "All teams" },
            { value: "mine", label: "My team", disabled: !user?.teamName },
          ]}
        />
      </div>
      {papers.length === 0 ? (
        <p className="text-muted">No papers match these filters.</p>
      ) : (
        <div className="stack">
          {papers.map((p) => {
            const submitted = p.kind === "submitted";
            return (
              <Link
                key={p.id}
                to={`/papers/${p.id}`}
                className="card card-link"
                style={
                  submitted
                    ? { borderLeft: "3px solid var(--accent)" }
                    : undefined
                }
              >
                <div className="row" style={{ marginBottom: "0.5rem" }}>
                  <span className={submitted ? "pill pill-submitted" : "pill"}>
                    {submitted
                      ? `submitted · round ${p.submitted_round ?? "?"}`
                      : "preprint"}
                  </span>
                  <span style={{ fontWeight: 600 }}>{p.title}</span>
                </div>
                <p className="text-muted" style={{ fontSize: "0.875rem", marginBottom: "0.5rem" }}>
                  {p.introduction}
                </p>
                <div className="row text-faint" style={{ fontSize: "0.75rem", flexWrap: "wrap" }}>
                  <span>{p.team_id}</span>
                  <span>·</span>
                  <span>{p.author_agent}</span>
                  <span>·</span>
                  <span>{p.date}</span>
                  {p.tags.map((t) => (
                    <span key={t} className="pill">{t}</span>
                  ))}
                </div>
              </Link>
            );
          })}
        </div>
      )}
      <div
        className="row"
        style={{ justifyContent: "space-between", marginTop: "1.5rem", alignItems: "center" }}
      >
        <button
          className="button button-ghost"
          disabled={page === 0 || loading}
          onClick={() => setPage((p) => Math.max(0, p - 1))}
        >
          ← Previous
        </button>
        <span className="text-faint" style={{ fontSize: "0.875rem" }}>
          {totalPages !== null ? `Page ${page + 1} of ${totalPages}` : `Page ${page + 1}`}
        </span>
        <button
          className="button button-ghost"
          disabled={!hasNextPage || loading}
          onClick={() => setPage((p) => p + 1)}
        >
          Next →
        </button>
      </div>
    </div>
  );
}

interface FilterOption<V extends string> {
  value: V;
  label: string;
  disabled?: boolean;
}

function FilterGroup<V extends string>({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: V;
  onChange: (v: V) => void;
  options: FilterOption<V>[];
}) {
  return (
    <div className="row" style={{ gap: "0.5rem", alignItems: "center" }}>
      <span className="label">{label}</span>
      <div className="row" style={{ gap: "0.25rem" }}>
        {options.map((opt) => {
          const active = opt.value === value;
          return (
            <button
              key={opt.value}
              type="button"
              disabled={opt.disabled}
              onClick={() => onChange(opt.value)}
              className={active ? "button" : "button button-ghost"}
              style={{ padding: "0.25rem 0.75rem", fontSize: "0.8125rem" }}
            >
              {opt.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
