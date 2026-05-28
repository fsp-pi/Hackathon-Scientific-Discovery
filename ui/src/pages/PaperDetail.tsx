import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import ReactMarkdown, { defaultUrlTransform } from "react-markdown";
import remarkGfm from "remark-gfm";

import { api } from "../api";
import type { PaperDetail } from "../types";

const DATA_IMAGE_RE = /^data:image\/(png|jpe?g|gif|webp);base64,/i;

function urlTransform(url: string, key: string, node: { tagName?: string }) {
  if (key === "src" && node.tagName === "img" && DATA_IMAGE_RE.test(url)) {
    return url;
  }
  return defaultUrlTransform(url);
}

export function PaperDetailPage() {
  const { id = "" } = useParams();
  const [paper, setPaper] = useState<PaperDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.papers
      .get(id)
      .then(setPaper)
      .catch((e) => setError(String(e)));
  }, [id]);

  if (error) return <p className="error">{error}</p>;
  if (!paper) return <p className="text-muted">Loading paper…</p>;

  return (
    <div className="stack">
      <Link to="/" className="text-faint" style={{ fontSize: "0.875rem" }}>← Browse</Link>

      <div>
        <div className="row" style={{ marginBottom: "0.5rem" }}>
          <span className={paper.kind === "submitted" ? "pill pill-submitted" : "pill"}>
            {paper.kind === "submitted"
              ? `submitted · round ${paper.submitted_round ?? "?"}`
              : "preprint"}
          </span>
          <span className="text-faint" style={{ fontFamily: "ui-monospace, monospace", fontSize: "0.75rem" }}>{paper.id}</span>
        </div>
        <h1 className="h1" style={{ marginBottom: "0.75rem" }}>{paper.title}</h1>
        <div className="row text-muted" style={{ fontSize: "0.875rem", flexWrap: "wrap" }}>
          <span>{paper.team_id}</span>
          <span>·</span>
          <span>{paper.author_agent}</span>
          <span>·</span>
          <span>{paper.date}</span>
          {paper.tags.map((t) => (
            <span key={t} className="pill">{t}</span>
          ))}
        </div>
      </div>

      <Section title="Introduction" body={paper.introduction} italic />
      <Section title="Methods" body={paper.methods} />
      <Section title="Results" body={paper.results} />
      {paper.references && <Section title="References" body={paper.references} />}
      {paper.appendix && <Section title="Appendix" body={paper.appendix} />}
    </div>
  );
}

function Section({ title, body, italic = false }: { title: string; body: string; italic?: boolean }) {
  return (
    <div>
      <div className="label" style={{ marginBottom: "0.35rem" }}>{title}</div>
      <div className={italic ? "markdown markdown-italic" : "markdown"}>
        <ReactMarkdown remarkPlugins={[remarkGfm]} urlTransform={urlTransform}>{body}</ReactMarkdown>
      </div>
    </div>
  );
}
