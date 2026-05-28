"""FastAPI server for UI."""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from typing import Optional
from hackathon_science.config import load_global_config, expand_path
from hackathon_science.git_ops import load_papers, pull_latest


app = FastAPI(title="Hackathon Science API")

# Enable CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_repo_path() -> Path:
    """Get shared repository path from config."""
    config = load_global_config()
    if config is None:
        raise HTTPException(status_code=500, detail="No global config found")
    return expand_path(config["shared_repo"]["local_path"])


@app.get("/api/papers")
async def list_papers():
    """List all papers."""
    repo_path = get_repo_path()
    papers = load_papers(repo_path)

    return [
        {
            "id": p.id,
            "title": p.title,
            "author": p.author,
            "date": p.date,
            "introduction": p.introduction,
            "tags": p.tags,
        }
        for p in papers
    ]


@app.get("/api/papers/{paper_id}")
async def get_paper(paper_id: str):
    """Get paper by ID."""
    repo_path = get_repo_path()
    papers = load_papers(repo_path)

    paper = next((p for p in papers if p.id == paper_id), None)
    if paper is None:
        raise HTTPException(status_code=404, detail="Paper not found")

    return {
        "id": paper.id,
        "title": paper.title,
        "author": paper.author,
        "date": paper.date,
        "introduction": paper.introduction,
        "methods": paper.methods,
        "results": paper.results,
        "references": paper.references,
        "appendix": paper.appendix,
        "tags": paper.tags,
    }


@app.get("/api/graph")
async def get_graph():
    """Get paper graph data (simplified - no citations)."""
    repo_path = get_repo_path()
    papers = load_papers(repo_path)

    # Build nodes (no edges since we removed cites)
    nodes = []

    # Create nodes
    for paper in papers:
        nodes.append({
            "id": paper.id,
            "title": paper.title,
            "author": paper.author,
            "date": paper.date,
            "tags": paper.tags,
        })

    return {
        "nodes": nodes,
        "edges": []  # No citation edges
    }


@app.post("/api/refresh")
async def refresh():
    """Pull latest from shared repository."""
    repo_path = get_repo_path()

    try:
        pull_latest(repo_path)
        return {"status": "success", "message": "Repository updated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7842)
