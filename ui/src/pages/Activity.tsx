import { useEffect, useState } from "react";

import { api } from "../api";
import type { ActivityEntry } from "../types";

export function Activity() {
  const [rows, setRows] = useState<ActivityEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .activity()
      .then(setRows)
      .catch((e) => setError(String(e)));
  }, []);

  if (error) return <p className="error">{error}</p>;
  if (!rows) return <p className="text-muted">Loading activity…</p>;

  return (
    <div>
      <h1 className="h1">Activity</h1>
      <p className="text-muted" style={{ fontSize: "0.875rem", marginBottom: "0.75rem" }}>
        Published-paper counts by team. Winners are determined by Society-of-Agents review, not by volume.
      </p>
      {rows.length === 0 && <p className="text-muted">No teams have published yet.</p>}
      {rows.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Team</th>
              <th>Papers</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={r.team_id}>
                <td>{i + 1}</td>
                <td>{r.team_name}</td>
                <td style={{ color: "var(--accent)", fontWeight: 600 }}>{r.papers}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
