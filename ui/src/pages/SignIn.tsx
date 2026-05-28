import { useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { autoSignIn, signIn, signUp } from "aws-amplify/auth";

import { api } from "../api";
import { slugify, useAuth } from "../auth";
import type { TeamSummary } from "../types";

type Mode = "sign-in" | "sign-up";

export function SignIn() {
  const navigate = useNavigate();
  const { refresh } = useAuth();
  const [mode, setMode] = useState<Mode>("sign-in");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [teamName, setTeamName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [teams, setTeams] = useState<TeamSummary[] | null>(null);

  useEffect(() => {
    if (mode !== "sign-up" || teams !== null) return;
    api.teamsPublic
      .list()
      .then(setTeams)
      .catch(() => setTeams([])); // fail soft — falls back to free-text entry
  }, [mode, teams]);

  const currentSlug = slugify(teamName);
  const matchingTeam = useMemo(
    () => teams?.find((t) => t.id === currentSlug) ?? null,
    [teams, currentSlug],
  );
  const suggestions = useMemo(() => {
    if (!teams) return [];
    const visible = teams.filter((t) => t.id !== "team-drew");
    const needle = teamName.trim().toLowerCase();
    const filtered = needle
      ? visible.filter(
          (t) =>
            t.id.includes(currentSlug) || t.name.toLowerCase().includes(needle),
        )
      : visible;
    return filtered.slice(0, 8);
  }, [teams, teamName, currentSlug]);

  async function submitSignIn(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const result = await signIn({
        username: email,
        password,
        options: { authFlowType: "USER_SRP_AUTH" },
      });
      if (result.nextStep.signInStep === "DONE") {
        await refresh();
        navigate("/");
      } else {
        setError(`Unexpected next step: ${result.nextStep.signInStep}`);
      }
    } catch (err) {
      const name = (err as { name?: string }).name;
      // First-time user: drop into sign-up with the email prefilled.
      if (name === "UserNotFoundException") {
        setMode("sign-up");
        setError(null);
      } else if (name === "NotAuthorizedException") {
        setError("Incorrect email or password.");
      } else {
        setError(formatError(err));
      }
    } finally {
      setBusy(false);
    }
  }

  async function submitSignUp(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const slug = slugify(teamName);
      if (!slug) {
        setError("Team name must contain at least one letter or digit.");
        setBusy(false);
        return;
      }
      // Pre-Signup Lambda auto-confirms + auto-verifies email, so signUp()
      // returns COMPLETE_AUTO_SIGN_IN directly (no email, no confirm step).
      const signUpResult = await signUp({
        username: email,
        password,
        options: {
          userAttributes: {
            email,
            "custom:team_name": slug,
          },
          autoSignIn: true,
        },
      });
      if (signUpResult.nextStep.signUpStep === "COMPLETE_AUTO_SIGN_IN") {
        const autoResult = await autoSignIn();
        if (autoResult.nextStep.signInStep === "DONE") {
          await refresh();
          navigate("/getting-started");
          return;
        }
        setError(
          `Unexpected sign-in step after sign-up: ${autoResult.nextStep.signInStep}`,
        );
        return;
      }
      setError(
        `Unexpected sign-up step: ${signUpResult.nextStep.signUpStep}`,
      );
    } catch (err) {
      setError(formatError(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="signin-shell">
      <h1 className="h1">{mode === "sign-in" ? "Sign in" : "Create account"}</h1>

      {mode === "sign-in" && (
        <form onSubmit={submitSignIn} className="stack">
          <label className="label" htmlFor="email">Email</label>
          <input
            id="email"
            type="email"
            required
            className="input"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
            autoFocus
          />
          <label className="label" htmlFor="password">Password</label>
          <input
            id="password"
            type="password"
            required
            className="input"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
          />
          <button
            type="submit"
            className="button"
            disabled={busy || !email || !password}
          >
            {busy ? "Signing in…" : "Sign in"}
          </button>
          <button
            type="button"
            className="button-link"
            onClick={() => {
              setMode("sign-up");
              setError(null);
            }}
          >
            New here? Create an account
          </button>
          {error && <p className="error">{error}</p>}
        </form>
      )}

      {mode === "sign-up" && (
        <form onSubmit={submitSignUp} className="stack">
          <label className="label" htmlFor="signup-email">Email</label>
          <input
            id="signup-email"
            type="email"
            required
            className="input"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
            autoFocus
          />
          <label className="label" htmlFor="signup-password">Password</label>
          <input
            id="signup-password"
            type="password"
            required
            className="input"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="new-password"
            minLength={8}
          />
          <label className="label" htmlFor="team">Team name</label>
          <input
            id="team"
            type="text"
            required
            className="input"
            value={teamName}
            onChange={(e) => setTeamName(e.target.value)}
            placeholder="Search existing teams or type a new name"
            autoComplete="off"
          />
          {teams && teams.length > 0 && suggestions.length > 0 && (
            <ul
              className="team-suggestions"
              style={{
                listStyle: "none",
                padding: 0,
                margin: 0,
                border: "1px solid var(--border, #ddd)",
                borderRadius: 4,
                maxHeight: 200,
                overflowY: "auto",
              }}
            >
              {suggestions.map((t) => {
                const active = t.id === currentSlug;
                return (
                  <li key={t.id}>
                    <button
                      type="button"
                      onClick={() => setTeamName(t.name)}
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        width: "100%",
                        padding: "0.5rem 0.75rem",
                        background: active ? "var(--accent-bg, #eef)" : "transparent",
                        border: "none",
                        borderBottom: "1px solid var(--border, #eee)",
                        cursor: "pointer",
                        textAlign: "left",
                        fontSize: "0.875rem",
                      }}
                    >
                      <span><code>{t.id}</code> {t.name !== t.id && <span className="text-faint">({t.name})</span>}</span>
                      <span className="text-faint" style={{ fontSize: "0.75rem" }}>
                        {t.members} {t.members === 1 ? "member" : "members"}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
          {teamName && (
            <p className="text-faint" style={{ fontSize: "0.75rem" }}>
              {!currentSlug
                ? "(needs at least one letter/digit)"
                : matchingTeam
                  ? <>You'll <b>join existing team</b> <code>{matchingTeam.id}</code> ({matchingTeam.members} {matchingTeam.members === 1 ? "member" : "members"}).</>
                  : <>You'll <b>create a new team</b> <code>{currentSlug}</code>.</>}
            </p>
          )}
          <button
            type="submit"
            className="button"
            disabled={busy || !email || !password || !currentSlug}
          >
            {busy ? "Creating…" : matchingTeam ? "Join team" : "Create account"}
          </button>
          <button
            type="button"
            className="button-link"
            onClick={() => {
              setMode("sign-in");
              setError(null);
            }}
          >
            Already have an account? Sign in
          </button>
          {error && <p className="error">{error}</p>}
        </form>
      )}
    </div>
  );
}

function formatError(err: unknown): string {
  const e = err as { name?: string; message?: string };
  if (e.message) return e.message;
  if (e.name) return e.name;
  return String(err);
}
