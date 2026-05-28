import { useState } from "react";
import type { FormEvent, ReactNode } from "react";

import { config } from "./config";

const STORAGE_KEY = "event-gate-ok";
const EVENT_PASSWORD = "BOSTechWeek";

function hasPassed(): boolean {
  if (config.localDev) return true;
  try {
    return localStorage.getItem(STORAGE_KEY) === "yes";
  } catch {
    return false;
  }
}

export function EventGate({ children }: { children: ReactNode }) {
  const [passed, setPassed] = useState(hasPassed);
  const [value, setValue] = useState("");
  const [error, setError] = useState<string | null>(null);

  if (passed) return <>{children}</>;

  function submit(e: FormEvent) {
    e.preventDefault();
    if (value === EVENT_PASSWORD) {
      try {
        localStorage.setItem(STORAGE_KEY, "yes");
      } catch {
        // localStorage unavailable (private mode etc.) — still let them in for this tab
      }
      setPassed(true);
    } else {
      setError("Incorrect password.");
    }
  }

  return (
    <div className="signin-shell">
      <h1 className="h1">Event access</h1>
      <form onSubmit={submit} className="stack">
        <label className="label" htmlFor="event-password">Password</label>
        <input
          id="event-password"
          type="password"
          required
          className="input"
          value={value}
          onChange={(e) => {
            setValue(e.target.value);
            if (error) setError(null);
          }}
          autoFocus
        />
        <button type="submit" className="button" disabled={!value}>
          Continue
        </button>
        {error && <p className="error">{error}</p>}
      </form>
    </div>
  );
}
