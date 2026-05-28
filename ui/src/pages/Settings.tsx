import { useEffect, useState } from "react";

import { api } from "../api";
import type { ApiKeyCreated, ApiKeySummary, BedrockCredentials } from "../types";

function formatRemaining(expiration: string): string {
  const ms = new Date(expiration).getTime() - Date.now();
  if (ms <= 0) return "expired";
  const totalSec = Math.floor(ms / 1000);
  const m = Math.floor(totalSec / 60);
  const s = totalSec % 60;
  return `${m}m ${s.toString().padStart(2, "0")}s`;
}

function bedrockExportBlock(c: BedrockCredentials): string {
  return [
    `export AWS_ACCESS_KEY_ID=${c.access_key_id}`,
    `export AWS_SECRET_ACCESS_KEY=${c.secret_access_key}`,
    `export AWS_SESSION_TOKEN=${c.session_token}`,
    `export AWS_REGION=${c.region}`,
  ].join("\n");
}

export function Settings() {
  const [keys, setKeys] = useState<ApiKeySummary[] | null>(null);
  const [name, setName] = useState("");
  const [justCreated, setJustCreated] = useState<ApiKeyCreated | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [creds, setCreds] = useState<BedrockCredentials | null>(null);
  const [mintBusy, setMintBusy] = useState(false);
  const [mintError, setMintError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [, setNow] = useState(0);

  useEffect(() => {
    if (!creds) return;
    const id = setInterval(() => setNow((n) => n + 1), 1000);
    return () => clearInterval(id);
  }, [creds]);

  async function mintBedrock() {
    setMintError(null);
    setCopied(false);
    setMintBusy(true);
    try {
      setCreds(await api.bedrockCredentials.mint());
    } catch (e) {
      const msg = String(e);
      setMintError(
        msg.includes("403")
          ? "Sign in again to mint credentials."
          : msg,
      );
    } finally {
      setMintBusy(false);
    }
  }

  async function copyCreds() {
    if (!creds) return;
    await navigator.clipboard.writeText(bedrockExportBlock(creds));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  async function refresh() {
    try {
      setKeys(await api.apiKeys.list());
    } catch (e) {
      setError(String(e));
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const created = await api.apiKeys.create(name);
      setJustCreated(created);
      setName("");
      await refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function revoke(id: number) {
    if (!confirm("Revoke this key? Any CLI using it will stop working.")) return;
    try {
      await api.apiKeys.revoke(id);
      await refresh();
    } catch (e) {
      setError(String(e));
    }
  }

  return (
    <div className="stack">
      <h1 className="h1">Settings</h1>

      <section className="card stack">
        <h2 style={{ fontSize: "1rem", fontWeight: 600 }}>CLI API Keys</h2>
        <p className="text-muted" style={{ fontSize: "0.875rem" }}>
          Generate a key, then run:
        </p>
        <pre className="code-block">
{`uv run hackathon login --api-key <paste-key>`}
        </pre>

        <form onSubmit={create} className="row" style={{ gap: "0.5rem" }}>
          <input
            type="text"
            className="input"
            placeholder="Key name (e.g. laptop)"
            value={name}
            onChange={(e) => setName(e.target.value)}
            style={{ flex: 1 }}
          />
          <button type="submit" className="button" disabled={busy}>
            {busy ? "Creating…" : "Create key"}
          </button>
        </form>

        {justCreated && (
          <div className="card" style={{ borderColor: "var(--accent)" }}>
            <p className="label" style={{ marginBottom: "0.5rem" }}>
              Copy this key — it won't be shown again
            </p>
            <pre className="code-block">{justCreated.token}</pre>
            <button
              className="button button-ghost"
              style={{ marginTop: "0.5rem" }}
              onClick={() => setJustCreated(null)}
            >
              Done
            </button>
          </div>
        )}

        {error && <p className="error">{error}</p>}

        {keys && keys.length > 0 && (
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Created</th>
                <th>Last used</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {keys.map((k) => (
                <tr key={k.id}>
                  <td>{k.name || <span className="text-faint">(unnamed)</span>}</td>
                  <td className="text-muted">{new Date(k.created_at).toLocaleString()}</td>
                  <td className="text-muted">
                    {k.last_used_at ? new Date(k.last_used_at).toLocaleString() : "never"}
                  </td>
                  <td>
                    <button className="button button-ghost" onClick={() => void revoke(k.id)}>
                      Revoke
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {keys && keys.length === 0 && (
          <p className="text-muted" style={{ fontSize: "0.875rem" }}>No keys yet.</p>
        )}
      </section>

      <section className="card stack">
        <h2 style={{ fontSize: "1rem", fontWeight: 600 }}>Bedrock Credentials</h2>
        <p className="text-muted" style={{ fontSize: "0.875rem" }}>
          Temporary AWS keys for <code>call_llm()</code> in your agent. Expire in
          1 hour. Don't commit. If you set up earlier in the day, click
          Regenerate right before the hackathon.
        </p>

        <button
          type="button"
          className="button"
          onClick={() => void mintBedrock()}
          disabled={mintBusy}
          style={{ alignSelf: "flex-start" }}
        >
          {mintBusy
            ? "Generating…"
            : creds
              ? "Regenerate"
              : "Generate Bedrock Credentials"}
        </button>

        {mintError && <p className="error">{mintError}</p>}

        {creds && (
          <div className="card" style={{ borderColor: "var(--accent)" }}>
            <p className="label" style={{ marginBottom: "0.5rem" }}>
              Paste into your shell. These won't be shown again.
            </p>
            <pre className="code-block">{bedrockExportBlock(creds)}</pre>
            <div className="row" style={{ gap: "0.5rem", marginTop: "0.5rem" }}>
              <button
                type="button"
                className="button button-ghost"
                onClick={() => void copyCreds()}
              >
                {copied ? "Copied" : "Copy"}
              </button>
              <span className="text-muted" style={{ fontSize: "0.875rem", alignSelf: "center" }}>
                Expires in {formatRemaining(creds.expiration)}
              </span>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
