# Agent rules

**Default assumption:** you are helping someone **write a paper-generation
agent** for the Hackathon Scientific Discovery platform. They are an end user
of the `hackathon` CLI, **not** a contributor to this repo's internals. Stay
in this mode unless the user says otherwise (e.g. "I'm working on the CLI",
"I'm fixing the cloud API", "this is for the hackathon platform itself", or
"I'm on the Pioneering Intelligence team"). When they do, switch into
contributor mode: edits to `hackathon_science/`, `ui/`, `infra/`, etc. are
then on the table.

## Default workflow

The user's code lives in `agents/<their-team>/`. Edit those files. Don't
touch `hackathon_science/`, `ui/`, or `infra/` unless they explicitly ask.

Their loop: edit `agents/<team>/my_run_agent.py` → `uv run hackathon run
agents/<team>/my_run_agent.py` → `uv run hackathon publish-to-ecosystem
<draft_id>`. Always prefix CLI commands with `uv run`.

## Agent contract

`my_run_agent.py` must export `run(problem_domain, papers_dir=None) -> Paper`.
The returned `Paper` needs non-empty `title`, `introduction`, `methods`,
`results`. `references`, `appendix`, `tags` are optional. See
`hackathon_science/models.py` for the full schema.

## Bedrock model IDs (load-bearing)

`call_llm()` uses AWS Bedrock Converse. **Use an inference-profile ID, not
a foundation-model ID.** On-demand Converse rejects foundation IDs with
`ValidationException: Invocation of model ID ... with on-demand throughput
isn't supported`.

Currently acceptable:
- `global.anthropic.claude-opus-4-7`
- `global.anthropic.claude-sonnet-4-6`

Notes:
- **No `-v1:0` suffix** on Sonnet 4.6+ / Opus 4.6+ inference profiles. The
  suffix exists on legacy IDs (e.g. `claude-3-5-sonnet-20241022-v2:0`) and
  on the raw foundation-model IDs, but not on the current global profiles.
- Raw `anthropic.claude-opus-4-7` (no prefix) is the foundation-model ID
  and is **not** callable via on-demand Converse.
- To list profiles available to the account:
  `aws bedrock list-inference-profiles --region us-east-1`.

## Auth + URL

Credentials live at `~/.hackathon-science/credentials`. `--api-url` must
include a scheme — schemeless paths like `/api` are rejected by `hackathon
login`. The default origin is `https://flagship-hackathon.com` and
the CLI auto-appends `/api`.

## Code style

Bias to minimalism. Don't add comments restating code, defensive checks for
impossible cases, premature abstractions, or wrapper functions with one
caller. If the user's existing agent is already terse and direct, leave it
alone.
