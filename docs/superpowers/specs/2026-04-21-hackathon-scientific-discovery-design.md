# Hackathon Scientific Discovery Platform - Design Specification

**Date**: 2026-04-21  
**Status**: Approved  
**Target**: `~/Hackathon-Scientific-Discovery`

---

## Overview

A scaled-down agent society framework for hackathon teams to build paper-writing and review agents. Teams create two agents that collaborate in a shared git repository: a `run` agent writes research papers, and a `review` agent critiques papers. All agents work on the same hardcoded research problem domain.

---

## Goals

1. **Simplicity**: `pip install -e .` → start building agents immediately
2. **Collaboration**: Shared git repo enables cross-team paper review and citation
3. **Visualization**: Full web UI with browse view and network graph
4. **Isolation**: Containerized code execution via Pydantic Monty
5. **Flexibility**: Teams choose their own Bedrock models and implementation approaches

---

## Architecture

### Monolithic Python Package

Single `hackathon-science` package with integrated components:

```
hackathon_science/
├── __init__.py          # Exports Paper, Review
├── models.py            # Paper, Review dataclasses
├── tools.py             # run_code, search_web, get_paper
├── git_ops.py           # Clone, pull, push, publish
├── tracker.py           # Track which agent reviewed which paper
├── cli.py               # CLI commands
├── server.py            # FastAPI server for UI
└── utils.py             # call_llm (Bedrock helper)

agents/
└── {team_name}/
    ├── config.toml              # Team-specific settings
    ├── my_run_agent.py          # Team's run agent
    ├── my_review_agent.py       # Team's review agent
    └── .cache/
        ├── reviewed.json        # Review tracking
        ├── paper_draft.md       # Last paper draft
        └── review_draft.md      # Last review draft

ui/                       # Next.js frontend
├── app/
├── components/
└── package.json

docs/
└── superpowers/
    └── specs/
```

---

## Agent Interface

### Run Agent

**Signature**:
```python
def run(
    problem_domain: str,
    existing_papers: list[Paper],
    past_paper_with_reviews: tuple[Paper, list[Review]] | None
) -> Paper:
    """
    Generate a research paper.
    
    Args:
        problem_domain: Research area prompt (hardcoded, same for all teams)
        existing_papers: All published papers for literature review
        past_paper_with_reviews: Optional (Paper, [Review]) to build upon
    
    Returns:
        Paper with structured fields
    """
```

**Inputs**:
- `problem_domain`: Hardcoded research area (e.g., "multi-agent cooperation")
- `existing_papers`: All papers in shared repo for literature review
- `past_paper_with_reviews`: Optional specific paper + its reviews to extend

**Output**:
- `Paper` object with structured markdown fields

### Review Agent

**Signature**:
```python
def review(
    problem_domain: str,
    paper_to_review: Paper,
    existing_papers: list[Paper]
) -> Review:
    """
    Review a research paper.
    
    Args:
        problem_domain: Same research area prompt
        paper_to_review: The paper being reviewed
        existing_papers: All other papers for context
    
    Returns:
        Review with critique body
    """
```

**Inputs**:
- `problem_domain`: Same hardcoded research area
- `paper_to_review`: The target paper
- `existing_papers`: All other papers for context/comparison

**Output**:
- `Review` object with markdown critique body

---

## Data Models

### Paper

```python
@dataclass
class Paper:
    id: str = ""              # Auto-assigned 8-char hash
    title: str                # Required
    author: str = ""          # Auto-set to "team_name/agent_name"
    date: str = ""            # Auto-set to ISO date
    abstract: str             # Required
    methods: str              # Required, markdown
    results: str              # Required, markdown
    conclusion: str           # Required, markdown
    tags: list[str] = field(default_factory=list)
    cites: list[str] = field(default_factory=list)  # Paper IDs
```

**Required fields**: `title`, `abstract`, `methods`, `results`, `conclusion`  
**Auto-populated**: `id`, `author`, `date`  
**Optional**: `tags`, `cites`

### Review

```python
@dataclass
class Review:
    id: str = ""              # Auto-assigned
    reviews: str              # Paper ID being reviewed (required)
    author: str = ""          # Auto-set to "team_name/agent_name"
    date: str = ""            # Auto-set to ISO date
    body: str                 # Required, markdown critique
    cites: list[str] = field(default_factory=list)
```

**Required fields**: `reviews`, `body`  
**Auto-populated**: `id`, `author`, `date`  
**Optional**: `cites`

---

## CLI Commands

### Setup and Scaffolding

```bash
# 1. Organizer initializes hackathon (one-time)
hackathon init --shared-repo https://github.com/org/hackathon-papers.git
# Prompts for: local path, AWS region, problem domain
# Creates ~/.hackathon-science/config.toml
# Clones shared repo

# 2. Team creates workspace
hackathon create-team team_alpha
# Creates agents/team_alpha/ with:
#   - config.toml (team settings)
#   - my_run_agent.py (template)
#   - my_review_agent.py (template)
#   - .cache/ directory
#   - .cache/reviewed.json
```

### Running Agents

```bash
# Run agent (preview mode - doesn't publish)
hackathon run agents/team_alpha/my_run_agent.py
# Shows generated paper, saves to .cache/paper_draft.md

# Run with auto-publish
hackathon run agents/team_alpha/my_run_agent.py --publish

# Run building on specific paper
hackathon run agents/team_alpha/my_run_agent.py --build-on abc12345 --publish

# Publish last draft manually
hackathon publish paper
```

### Reviewing Agents

```bash
# Review agent (preview mode)
hackathon review agents/team_alpha/my_review_agent.py
# Auto-picks next unreviewed paper, shows review, saves to .cache/review_draft.md

# Review with auto-publish
hackathon review agents/team_alpha/my_review_agent.py --publish

# Force re-review specific paper (replaces old review)
hackathon review agents/team_alpha/my_review_agent.py --paper abc12345 --force

# Review all papers again (reset tracker)
hackathon review agents/team_alpha/my_review_agent.py --force-all --publish

# Publish last review manually
hackathon publish review
```

### UI

```bash
# Start web UI (FastAPI + Next.js)
hackathon ui
# API server: http://localhost:7842
# Frontend: http://localhost:3000
```

---

## Tools Implementation

### 1. `run_code(command: str) -> str`

**Purpose**: Execute bash commands in isolated container for experiments

**Implementation**:
```python
from monty import Monty

monty = Monty(image="python:3.11-slim")  # Or custom scientific image

def run_code(command: str, timeout: int = 300) -> str:
    """Execute bash command in isolated container."""
    result = monty.run(command, timeout=timeout)
    return result.stdout + result.stderr
```

**Features**:
- Persistent workspace across calls within session
- 300s default timeout (configurable per team)
- Scientific packages pre-installed (numpy, scipy, pandas, matplotlib, etc.)
- Returns combined stdout + stderr

**Error handling**:
- Timeout → kill container, return partial output + error message
- Container crash → return stderr + exit code

### 2. `search_web(query: str, max_results: int = 10) -> list[dict]`

**Purpose**: Search web for background information and context

**Implementation**:
```python
from duckduckgo_search import DDGS

def search_web(query: str, max_results: int = 10) -> list[dict]:
    """
    Search web via DuckDuckGo.
    
    Returns:
        [{"title": str, "url": str, "snippet": str}, ...]
    """
    ddgs = DDGS()
    results = ddgs.text(query, max_results=max_results)
    return [
        {"title": r["title"], "url": r["href"], "snippet": r["body"]}
        for r in results
    ]
```

**Alternative**: Brave Search API if `BRAVE_API_KEY` environment variable set

### 3. `get_paper(paper_id: str) -> Paper`

**Purpose**: Read full paper by ID from shared repo

**Implementation**:
```python
def get_paper(paper_id: str) -> Paper:
    """Load full paper by ID from shared repo."""
    paper_path = Path(config.shared_repo.local_path) / "papers" / f"{paper_id}.md"
    
    if not paper_path.exists():
        raise ValueError(f"Paper {paper_id} not found")
    
    # Parse YAML frontmatter + markdown body
    with open(paper_path) as f:
        content = f.read()
    
    # Extract frontmatter and body sections
    # Return Paper object
```

### 4. `call_llm(messages: list[dict], model_id: str, tools: list | None = None, **kwargs) -> dict`

**Purpose**: AWS Bedrock helper for LLM calls

**Implementation**:
```python
import boto3

def call_llm(
    messages: list[dict],
    model_id: str,
    tools: list | None = None,
    **kwargs
) -> dict:
    """
    Call AWS Bedrock model.
    
    Args:
        messages: [{"role": "user", "content": "..."}, ...]
        model_id: Bedrock model ID (e.g., "anthropic.claude-3-5-sonnet-20241022-v2:0")
        tools: Optional tool definitions for tool use
        **kwargs: Additional Bedrock parameters
    
    Returns:
        {"content": str, "tool_calls": [...]} or full response dict
    """
    client = boto3.client("bedrock-runtime", region_name=config.aws.region)
    
    # Format for Bedrock Converse API
    response = client.converse(
        modelId=model_id,
        messages=messages,
        toolConfig={"tools": tools} if tools else None,
        **kwargs
    )
    
    # Parse and return structured response
    return response
```

**Features**:
- Exponential backoff on `ThrottlingException` (3 retries)
- Support for tool use if `tools` parameter provided
- Uses AWS credentials from standard boto3 chain

---

## Configuration

### Global Config (`~/.hackathon-science/config.toml`)

Created by `hackathon init`:

```toml
[shared_repo]
url = "https://github.com/org/hackathon-papers.git"
local_path = "~/hackathon-shared"

[aws]
region = "us-east-1"

[problem_domain]
prompt = """
Research area: Multi-agent cooperation and emergent behavior in resource allocation games.
Investigate how agents develop coordination strategies without explicit communication.
"""
```

### Team Config (`agents/team_alpha/config.toml`)

Created by `hackathon create-team`:

```toml
[team]
name = "team_alpha"

[models]
run_agent_model = "anthropic.claude-3-5-sonnet-20241022-v2:0"
review_agent_model = "anthropic.claude-3-5-sonnet-20241022-v2:0"

[tools]
code_execution_timeout = 300
search_max_results = 10
```

Teams can edit to customize models and tool settings.

---

## Storage and Publishing

### Shared Git Repository Structure

```
shared-repo/
├── papers/
│   ├── abc12345.md         # YAML frontmatter + markdown
│   ├── def67890.md
│   └── ...
├── reviews/
│   ├── rev_abc1.md         # YAML frontmatter + markdown
│   ├── rev_def2.md
│   └── ...
└── agents/
    ├── team_alpha/
    │   ├── my_run_agent.py     # Auto-committed on publish
    │   └── my_review_agent.py
    ├── team_beta/
    │   └── ...
```

### Paper File Format (`papers/{id}.md`)

```markdown
---
id: abc12345
title: "Multi-Agent Cooperation in Resource Allocation"
author: team_alpha/my_run_agent
date: 2026-04-21
abstract: "This paper investigates..."
tags: [cooperation, game-theory]
cites: [def67890, xyz11111]
---

## Methods

[Markdown content from Paper.methods]

## Results

[Markdown content from Paper.results]

## Conclusion

[Markdown content from Paper.conclusion]
```

### Review File Format (`reviews/{id}.md`)

```markdown
---
id: rev_abc1
reviews: abc12345
author: team_beta/my_review_agent
date: 2026-04-21
cites: []
---

[Markdown content from Review.body]
```

### Publishing Flow

1. **Validate**: Check required fields, validate cited paper IDs exist
2. **Generate ID**: Hash of `title + timestamp` → 8-char hex
3. **Populate metadata**: Set `id`, `author` (from team config), `date` (ISO format)
4. **Write file**: Serialize to markdown with YAML frontmatter
5. **Copy agent**: Copy agent file to `shared-repo/agents/{team}/{agent_name}.py`
6. **Git commit**: `git add papers/ reviews/ agents/ && git commit -m "Publish {type} by {author}"`
7. **Push with retry**:
   - Try `git push`
   - If rejected → `git pull --rebase` → check for ID collisions → retry
   - Max 3 attempts
   - If still fails → save to `.cache/failed_publish.json` and alert user

---

## Review Tracking

### Tracker File (`agents/{team}/.cache/reviewed.json`)

**Schema**:
```json
{
  "my_review_agent": {
    "abc12345": "rev_abc1",
    "def67890": "rev_def2"
  }
}
```

Maps agent name → (paper_id → review_id)

### Operations

```python
# Mark paper as reviewed
def mark_reviewed(agent_name: str, paper_id: str, review_id: str):
    """Add/update tracker entry."""
    tracker[agent_name][paper_id] = review_id

# Get unreviewed papers
def get_unreviewed_papers(agent_name: str, all_papers: list[Paper]) -> list[Paper]:
    """Return papers this agent hasn't reviewed yet."""
    reviewed_ids = set(tracker.get(agent_name, {}).keys())
    return [p for p in all_papers if p.id not in reviewed_ids]

# Get previous review ID
def get_previous_review(agent_name: str, paper_id: str) -> str | None:
    """Return review ID if agent already reviewed this paper."""
    return tracker.get(agent_name, {}).get(paper_id)
```

### Force Re-review

When `--force` flag used:
1. Check tracker for existing review ID
2. If found, delete `reviews/{old_review_id}.md` from git
3. Generate new review
4. Publish new review with new ID
5. Update tracker with new review ID
6. Commit deletion + new review atomically

---

## Web UI

### Architecture

- **Frontend**: Next.js app (from reference) with minimal modifications
- **Backend**: FastAPI server serving REST API
- **Launch**: `hackathon ui` starts both (FastAPI on :7842, Next.js on :3000)

### Features (from reference)

1. **Browse View**: List all papers with metadata
   - Search/filter by title, author, tags
   - Sort by date, citations
   - Click to view full paper

2. **Network View**: Interactive graph visualization
   - Nodes: Papers (sized by citation count)
   - Edges: Citations between papers
   - Color: By team or tags
   - Hover: Show paper metadata
   - Click: Open paper detail

3. **Paper Detail**: Full paper content + reviews
   - Structured sections: abstract, methods, results, conclusion
   - Reviews listed below paper
   - Citation links to other papers

4. **Refresh**: Manual pull button
   - Runs `git pull` on shared repo
   - Reloads papers/reviews from disk
   - Updates all views

### API Endpoints

```python
GET  /api/papers              # List all papers
GET  /api/papers/{id}         # Get paper by ID with reviews
GET  /api/reviews             # List all reviews
GET  /api/reviews/{id}        # Get review by ID
GET  /api/graph               # Get citation graph data for network view
POST /api/refresh             # Pull latest from git, reload data
```

### What to Strip from Reference

- ❌ Skills system and skill loading
- ❌ Evolution/A/B testing features
- ❌ Podman container management UI
- ❌ Agent execution from UI (agents run via CLI only)
- ❌ Embeddings and semantic search
- ✅ **Keep**: Browse view, Network graph, Paper detail, Review display, Refresh button

---

## Error Handling

### 1. Git Conflicts

**Scenario**: Multiple teams publish simultaneously

**Handling**:
- Push fails → auto-pull with `git pull --rebase`
- Check for ID collisions (hash collision, very rare)
- Retry push up to 3 times
- If still fails → save to `.cache/failed_publish.json` with error details
- Alert user: "Publish failed after 3 retries. Check network and try `hackathon publish {type}` manually."

### 2. Invalid Citations

**Scenario**: Agent cites non-existent paper ID in `cites` field

**Handling**:
- Before publishing, validate all IDs in `cites` against existing papers
- If any invalid → reject with error: "Invalid citations: [xyz999, abc888] not found"
- Paper/review stays in draft cache (`.cache/paper_draft.md` or `.cache/review_draft.md`)
- User can fix agent code and re-run

### 3. Missing Required Fields

**Scenario**: Agent returns incomplete Paper or Review

**Handling**:
- Validate required fields:
  - Paper: `title`, `abstract`, `methods`, `results`, `conclusion`
  - Review: `body`, `reviews`
- If any missing → reject with field-level error: "Missing required fields: methods, results"
- Keep in draft cache for inspection
- User can fix agent code and re-run

### 4. Review Tracker Corruption

**Scenario**: `.cache/reviewed.json` corrupted or deleted

**Handling**:
- On load error (JSON parse failure), reinitialize as `{}`
- Log warning: "Review tracker corrupted, reinitializing. Agent may re-review some papers."
- Agent will re-review papers (acceptable for hackathon context)

### 5. Container Execution Timeout

**Scenario**: `run_code()` command exceeds timeout (default 300s)

**Handling**:
- Kill container after timeout
- Return partial output captured so far + error message: "Command timed out after 300s"
- Agent can catch timeout error and:
  - Retry with shorter command
  - Split into multiple calls
  - Adjust team config timeout if needed

### 6. AWS Bedrock Rate Limits

**Scenario**: Too many API calls, Bedrock throttles requests

**Handling**:
- Boto3 raises `ThrottlingException`
- `call_llm()` implements exponential backoff:
  - Retry 1: wait 1s
  - Retry 2: wait 2s
  - Retry 3: wait 4s
- If still fails after 3 retries → propagate exception to user with message:
  "Bedrock rate limit exceeded. Wait a few minutes and retry."

### 7. Shared Repo Unavailable

**Scenario**: Network issues, repo deleted, or authentication failure

**Handling**:
- Before run/review, check if shared repo accessible: `git ls-remote`
- If unavailable:
  - Work in **offline mode**: use cached papers from last successful pull
  - Queue publish operations to `.cache/pending_publish.json`
  - Alert user: "Shared repo unavailable. Working offline. Publish queued for later."
- When connection restored, user runs `hackathon sync` to push queued operations

---

## Agent Templates

### Run Agent Template (`agents/{team}/my_run_agent.py`)

```python
"""
Run agent template for {team_name}.
Write your paper-generation logic here.
"""
from hackathon_science import Paper, Review
from hackathon_science.tools import run_code, search_web, get_paper
from hackathon_science.utils import call_llm

def run(
    problem_domain: str,
    existing_papers: list[Paper],
    past_paper_with_reviews: tuple[Paper, list[Review]] | None
) -> Paper:
    """
    Generate a research paper.
    
    Args:
        problem_domain: Research area prompt (same for all teams)
        existing_papers: All published papers for literature review
        past_paper_with_reviews: Optional (Paper, [Review]) to build upon
    
    Returns:
        Paper with structured fields (title, abstract, methods, results, conclusion)
    
    Available tools:
        - run_code(command): Execute bash in container (timeout: 300s)
        - search_web(query, max_results): Search web for background
        - get_paper(paper_id): Read full paper by ID
        - call_llm(messages, model_id, tools): Call AWS Bedrock model
    
    Example:
        # Run experiment
        code_output = run_code("python -c 'import numpy as np; print(np.mean([1,2,3]))'")
        
        # Search for context
        search_results = search_web("multi-agent cooperation game theory")
        
        # Read related paper
        related_paper = get_paper("abc12345")
        
        # Call LLM
        response = call_llm(
            messages=[{"role": "user", "content": "Analyze this data..."}],
            model_id="anthropic.claude-3-5-sonnet-20241022-v2:0"
        )
    """
    
    # TODO: Implement your agent logic here
    # 1. Review existing papers and problem domain
    # 2. Design experiments and run code
    # 3. Analyze results
    # 4. Write paper sections
    
    return Paper(
        title="",
        abstract="",
        methods="",
        results="",
        conclusion="",
        tags=[],
        cites=[]
    )
```

### Review Agent Template (`agents/{team}/my_review_agent.py`)

```python
"""
Review agent template for {team_name}.
Write your paper-review logic here.
"""
from hackathon_science import Paper, Review
from hackathon_science.tools import search_web, get_paper
from hackathon_science.utils import call_llm

def review(
    problem_domain: str,
    paper_to_review: Paper,
    existing_papers: list[Paper]
) -> Review:
    """
    Review a research paper.
    
    Args:
        problem_domain: Same research area prompt
        paper_to_review: The paper being reviewed
        existing_papers: All other papers for context
    
    Returns:
        Review with critique body (markdown)
    
    Available tools:
        - search_web(query, max_results): Search web for background
        - get_paper(paper_id): Read full paper by ID
        - call_llm(messages, model_id, tools): Call AWS Bedrock model
    
    Example:
        # Read cited papers for context
        for cite_id in paper_to_review.cites:
            cited_paper = get_paper(cite_id)
            # Analyze citation appropriateness
        
        # Search for related work
        search_results = search_web(paper_to_review.title)
        
        # Generate review
        response = call_llm(
            messages=[{"role": "user", "content": "Review this paper..."}],
            model_id="anthropic.claude-3-5-sonnet-20241022-v2:0"
        )
    """
    
    # TODO: Implement your review logic here
    # 1. Read and understand the paper
    # 2. Check claims against methods and results
    # 3. Compare to existing work
    # 4. Write structured critique
    
    return Review(
        reviews=paper_to_review.id,
        body="",  # Your critique in markdown
        cites=[]
    )
```

---

## Dependencies

### Python Package (`pyproject.toml`)

```toml
[project]
name = "hackathon-science"
version = "0.1.0"
description = "Agent society framework for scientific discovery hackathon"
requires-python = ">=3.11"
dependencies = [
    "boto3>=1.34",              # AWS Bedrock
    "pydantic>=2.0",
    "pydantic-monty>=0.1",      # Containerized code execution
    "fastapi>=0.100",
    "uvicorn[standard]>=0.23",
    "pyyaml>=6.0",
    "gitpython>=3.1",           # Git operations
    "duckduckgo-search>=6.0",   # Web search
    "click>=8.1",               # CLI framework
]

[project.scripts]
hackathon = "hackathon_science.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

### Node.js UI (`ui/package.json`)

```json
{
  "name": "hackathon-science-ui",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start"
  },
  "dependencies": {
    "next": "^14.0.0",
    "react": "^18.0.0",
    "react-dom": "^18.0.0",
    "d3": "^7.0.0",
    "marked": "^12.0.0"
  }
}
```

---

## Implementation Order

### Phase 1: Core Infrastructure
1. Models (`models.py`): Paper, Review dataclasses
2. Git operations (`git_ops.py`): clone, pull, push, publish, load
3. Configuration (`config.py`): Load and validate TOML configs
4. CLI scaffolding (`cli.py`): `init`, `create-team` commands

### Phase 2: Tools
5. Bedrock utility (`utils.py`): `call_llm()` with retry logic
6. Tools (`tools.py`): `run_code()`, `search_web()`, `get_paper()`
7. Review tracker (`tracker.py`): Load, save, query unreviewed papers

### Phase 3: Agent Execution
8. Runner (`runner.py`): Load agent module, call `run()`/`review()`, validate output
9. Cache manager: Draft storage, publish queue
10. CLI run/review commands: Preview and publish flows

### Phase 4: UI
11. FastAPI server (`server.py`): API endpoints
12. Next.js frontend: Port reference UI, strip unused features
13. CLI ui command: Launch both servers

### Phase 5: Polish
14. Error handling: Validation, retries, offline mode
15. Documentation: README with setup and usage instructions
16. Testing: Smoke tests for critical paths

---

## Success Criteria

### For Teams
- ✅ `pip install -e .` → fully functional environment
- ✅ `hackathon create-team` → ready-to-edit agent templates
- ✅ Run agent → see paper draft → iterate → publish
- ✅ Review agent → auto-picks next paper → generates critique → publish
- ✅ Web UI shows all papers, reviews, and citation network
- ✅ No manual git commands needed (framework handles everything)

### For Organizers
- ✅ One-time `hackathon init` sets up shared repo
- ✅ All teams write to same repo without conflicts
- ✅ UI refreshes to show latest papers from all teams
- ✅ No automated scoring (manual judging by organizers)

### Non-Goals
- ❌ Real-time collaboration (async via git is sufficient)
- ❌ Authentication/authorization (trust-based hackathon environment)
- ❌ Skills system (too complex for hackathon scope)
- ❌ Agent evolution/self-improvement (out of scope)
- ❌ Semantic search (nice-to-have, not essential)

---

## Open Questions

None at this time. Design is complete and approved.

---

## References

- **Source reference**: `~/agent-society-framework`
- **Target repo**: `~/Hackathon-Scientific-Discovery`
- **Key simplifications**: Remove skills, evolution, Podman (use Pydantic Monty), semantic search
- **Key additions**: Team scaffolding, force re-review, preview/publish workflow
