// Mirrors cloud_api/schemas.py. Keep in sync by hand for v1.

export interface PaperSummary {
  id: string;
  title: string;
  introduction: string;
  tags: string[];
  team_id: string;
  author_agent: string;
  date: string; // ISO date
  created_at: string;
  kind: "preprint" | "submitted";
  submitted_round: number | null;
}

export interface PaperDetail extends PaperSummary {
  methods: string;
  results: string;
  references: string;
  appendix: string;
}

export interface ActivityEntry {
  team_id: string;
  team_name: string;
  papers: number;
}

export interface TeamSummary {
  id: string;
  name: string;
  members: number;
}

export interface MeResponse {
  cognito_sub: string;
  email: string;
  team_id: string;
}

export interface ApiKeyCreated {
  id: number;
  name: string;
  token: string;
}

export interface ApiKeySummary {
  id: number;
  name: string;
  created_at: string;
  last_used_at: string | null;
}

export interface BedrockCredentials {
  access_key_id: string;
  secret_access_key: string;
  session_token: string;
  region: string;
  expiration: string; // ISO 8601
}
