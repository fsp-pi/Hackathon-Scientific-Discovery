# Stress test

Bulk-publish synthetic papers to exercise the cloud API and Browse pagination.

```
uv run python scripts/stress-test/publish_papers.py [N] [P]
```

- `N` — total papers to publish (default 50)
- `P` — parallel workers (default 16)

Run `uv run hackathon login --api-key <key>` first so credentials live at
`~/.hackathon-science/credentials`.

The papers are templated and contain no real content; tags include
`stress-test` so they're easy to identify and clean up.
