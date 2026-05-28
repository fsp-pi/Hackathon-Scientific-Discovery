import { createContext, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import {
  fetchAuthSession,
  getCurrentUser,
  signOut as amplifySignOut,
} from "aws-amplify/auth";

import { config } from "./config";

interface SignedInUser {
  email: string;
  sub: string;
  teamName: string;
}

/** Lowercase, alphanumeric, hyphens only. Single source of truth for how
 * a team name string becomes a team id — used at sign-up (to write the
 * Cognito attribute) and on read (to normalise legacy accounts that
 * registered before slugification landed). */
export function slugify(raw: string): string {
  return raw
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .replace(/-+/g, "-");
}

interface AuthContextValue {
  user: SignedInUser | null;
  loading: boolean;
  refresh: () => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

async function loadUser(): Promise<SignedInUser | null> {
  if (config.localDev) {
    return { email: "dev@localhost", sub: "local-dev-user", teamName: "local-team" };
  }
  try {
    const session = await fetchAuthSession();
    const idToken = session.tokens?.idToken;
    if (!idToken) return null;
    const payload = idToken.payload as Record<string, unknown>;
    const cognitoUser = await getCurrentUser();
    const rawTeam = (payload["custom:team_name"] as string) ?? "";
    return {
      email: (payload.email as string) ?? cognitoUser.signInDetails?.loginId ?? "",
      sub: cognitoUser.userId,
      teamName: slugify(rawTeam),
    };
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<SignedInUser | null>(null);
  const [loading, setLoading] = useState(true);

  async function refresh() {
    setLoading(true);
    setUser(await loadUser());
    setLoading(false);
  }

  useEffect(() => {
    void refresh();
  }, []);

  async function signOut() {
    await amplifySignOut();
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, loading, refresh, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
