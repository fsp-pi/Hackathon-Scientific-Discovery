# Local dev

Runs the cloud API against a Postgres in Docker, with auth bypassed so you
don't need Cognito. Used for verifying changes to `cloud_api/` without
deploying.

## Boot

```
./scripts/dev/up.sh
```

This:
1. Starts Postgres 16 in Docker (port 5433, named volume).
2. Sources `scripts/dev/.env` (LOCAL_DEV=1 + DB credentials).
3. Runs `uvicorn cloud_api.main:app` with the API-stack deps pulled in via
   `uv run --with` (so we don't pollute the project's pyproject lockfile).

When LOCAL_DEV=1 every authenticated route auto-resolves to a fixed
identity:

- team_id: `local-team`
- cognito_sub: `local-dev-user`
- email: `dev@localhost`

The bypass is a single `os.environ.get("LOCAL_DEV") == "1"` short-circuit
in `cloud_api/auth.py` and is impossible to enable in production unless
someone deliberately sets that var.

## Probe

```
curl http://localhost:8000/health                  # liveness
curl http://localhost:8000/api/papers              # paginated list
curl -i 'http://localhost:8000/api/papers?limit=5&offset=10'   # see X-Total-Count
```

## Stress-test against local

The CLI and `scripts/stress-test/publish_papers.py` both honor
`HACKATHON_API_URL` / `HACKATHON_API_KEY` env vars, which override the
`~/.hackathon-science/credentials` file. Auth-bypass mode ignores the key
value, so any string works:

```
HACKATHON_API_URL=http://localhost:8000/api \
HACKATHON_API_KEY=ignored \
  uv run python scripts/stress-test/publish_papers.py 500 16
```

(Local hits ~400 papers/sec since there's no network.)

## Tear down

```
./scripts/dev/down.sh             # stop container, keep data
./scripts/dev/down.sh --volumes   # stop and wipe DB
```

## Browse-tab UI against local

The SPA also has a `VITE_LOCAL_DEV=1` short-circuit that fakes a Cognito
session and bypasses the event-gate password. To run it:

```
cp ui/.env.example ui/.env.local
cd ui && npm install && npm run dev
```

Open http://localhost:5173. Browse should load against the local API
without sign-in. (The Settings page won't fully work — you can't mint
real API keys without a real Cognito session — but pagination, paper
detail, and activity all work end-to-end.)
