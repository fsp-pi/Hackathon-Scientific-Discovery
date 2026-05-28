import { fetchAuthSession } from "aws-amplify/auth";

import { config } from "./config";
import type {
  ApiKeyCreated,
  ApiKeySummary,
  BedrockCredentials,
  ActivityEntry,
  MeResponse,
  PaperDetail,
  PaperSummary,
  TeamSummary,
} from "./types";

async function authHeader(): Promise<Record<string, string>> {
  if (config.localDev) {
    return { Authorization: "Bearer local-dev-stub" };
  }
  const session = await fetchAuthSession();
  const token = session.tokens?.idToken?.toString();
  if (!token) throw new Error("not signed in");
  return { Authorization: `Bearer ${token}` };
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = {
    "Content-Type": "application/json",
    ...(await authHeader()),
    ...(init.headers ?? {}),
  };
  const res = await fetch(`${config.apiUrl}${path}`, { ...init, headers });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      // body wasn't json
    }
    throw new Error(`${res.status} ${detail}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

async function requestWithMeta<T>(
  path: string,
): Promise<{ data: T; total: number | null }> {
  const headers = {
    "Content-Type": "application/json",
    ...(await authHeader()),
  };
  const res = await fetch(`${config.apiUrl}${path}`, { headers });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      // body wasn't json
    }
    throw new Error(`${res.status} ${detail}`);
  }
  // Older API versions and some proxies drop custom response headers. Return
  // null in that case so callers can distinguish "unknown total" from "zero".
  const raw = res.headers.get("X-Total-Count");
  const total = raw === null ? null : Number(raw);
  const data = (await res.json()) as T;
  return { data, total };
}

async function requestPublic<T>(path: string): Promise<T> {
  const res = await fetch(`${config.apiUrl}${path}`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

export const api = {
  me: () => request<MeResponse>("/me"),
  teamsPublic: {
    list: () => requestPublic<TeamSummary[]>("/teams"),
  },
  papers: {
    list: (
      limit = 25,
      offset = 0,
      opts: {
        teamId?: string;
        kind?: "preprint" | "submitted";
        submittedRound?: number;
      } = {},
    ) => {
      const params = new URLSearchParams({
        limit: String(limit),
        offset: String(offset),
      });
      if (opts.teamId) params.set("team_id", opts.teamId);
      if (opts.kind) params.set("kind", opts.kind);
      if (opts.submittedRound !== undefined)
        params.set("submitted_round", String(opts.submittedRound));
      return requestWithMeta<PaperSummary[]>(`/papers?${params.toString()}`);
    },
    get: (id: string) => request<PaperDetail>(`/papers/${id}`),
  },
  activity: () => request<ActivityEntry[]>("/activity"),
  apiKeys: {
    list: () => request<ApiKeySummary[]>("/api-keys"),
    create: (name: string) =>
      request<ApiKeyCreated>("/api-keys", {
        method: "POST",
        body: JSON.stringify({ name }),
      }),
    revoke: (id: number) =>
      request<void>(`/api-keys/${id}`, { method: "DELETE" }),
  },
  bedrockCredentials: {
    mint: () =>
      request<BedrockCredentials>("/settings/bedrock-credentials", {
        method: "POST",
      }),
  },
};
