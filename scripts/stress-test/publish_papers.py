"""Bulk-publish synthetic papers to stress-test the cloud API.

Self-contained: no LLM calls, no dependency on `agents/`. Generates templated
papers in-process and POSTs to `/papers` via a thread pool sharing one auth
session, so throughput is bounded by the API rather than client startup.

Usage:
    uv run python scripts/stress-test/publish_papers.py [N] [P]

    N: total papers to publish (default 50)
    P: parallel workers           (default 16)

Requires `hackathon login` to have been run first (so credentials live at
~/.hackathon-science/credentials).
"""
from __future__ import annotations

import random
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from hackathon_science import Paper
from hackathon_science.cli import _short_id
from hackathon_science.cloud_client import CloudClient


ADJECTIVES = [
    "Quantum", "Stochastic", "Adversarial", "Federated", "Sparse",
    "Hierarchical", "Differentiable", "Self-Supervised", "Bayesian",
    "Topological", "Emergent", "Recursive", "Continual", "Convex",
    "Non-Convex", "Geometric", "Symplectic", "Equivariant", "Causal",
    "Counterfactual", "Probabilistic", "Variational", "Amortized",
    "Compositional", "Modular", "Disentangled", "Invariant", "Hyperbolic",
    "Riemannian", "Spectral", "Multimodal", "Cross-Lingual", "Few-Shot",
    "Zero-Shot", "In-Context", "Retrieval-Augmented", "Mixture-Of-Experts",
    "Sparse-Attention", "Linear-Time", "Sub-Quadratic", "Memory-Efficient",
    "Energy-Based", "Score-Based", "Flow-Based", "Implicit", "Explicit",
    "Neural-Symbolic", "Distributed", "Decentralized", "Asynchronous",
]

NOUNS = [
    "Transformers", "Manifolds", "Diffusion Models", "Graph Networks",
    "Reinforcement Loops", "Energy Functions", "Spectral Embeddings",
    "Latent Codes", "Attention Heads", "Mixture Experts", "World Models",
    "Kernel Machines", "Capsule Networks", "Hypernetworks", "Neural ODEs",
    "Normalizing Flows", "State-Space Models", "Recurrent Cells",
    "Memory Augmented Networks", "Belief Propagation", "Message Passing",
    "Contrastive Learners", "Autoencoders", "Variational Inference",
    "Monte Carlo Estimators", "Gradient Estimators", "Policy Gradients",
    "Q-Functions", "Value Networks", "Actor-Critic Agents", "World Simulators",
    "Causal Graphs", "Bayesian Networks", "Markov Chains", "Information Bottlenecks",
    "Attention Mechanisms", "Position Encodings", "Token Routers",
    "Retrieval Indexes", "Knowledge Graphs", "Symbolic Reasoners",
]

DOMAINS = [
    "protein folding", "climate modeling", "high-energy physics",
    "materials discovery", "neural decoding", "swarm robotics",
    "computational ethics", "autonomous theorem proving",
    "quantum chemistry", "exoplanet detection", "gravitational wave analysis",
    "cell-type classification", "single-cell transcriptomics",
    "drug-target interaction", "retrosynthetic planning",
    "fluid dynamics simulation", "plasma confinement",
    "seismic inversion", "ocean current modeling", "wildfire spread prediction",
    "epidemic forecasting", "antibiotic resistance prediction",
    "cryo-EM reconstruction", "molecular docking", "catalyst design",
    "battery electrolyte design", "superconductor discovery",
    "dark matter halo identification", "stellar spectroscopy",
    "weather nowcasting", "auroral physics", "tokamak plasma control",
    "quantum error correction", "lattice QCD", "string landscape exploration",
]

CITATIONS = [
    "Vaswani et al. (2017)", "LeCun & Bengio (2015)", "Hochreiter (1997)",
    "Goodfellow et al. (2014)", "Kingma & Welling (2014)", "Ho et al. (2020)",
    "Schulman et al. (2017)", "Mnih et al. (2015)", "Silver et al. (2017)",
    "Brown et al. (2020)", "Devlin et al. (2019)", "Radford et al. (2021)",
    "He et al. (2016)", "Krizhevsky et al. (2012)", "Lecun et al. (1998)",
    "Sutton & Barto (2018)", "Bishop (2006)", "MacKay (2003)",
]

INTRO_SENTENCES = [
    "Recent advances in {adj_l} {noun_l} have transformed the landscape of {domain}.",
    "Despite progress, {domain} remains challenging due to high-dimensional structure.",
    "Prior work {cite} demonstrated that representation learning can mitigate sample complexity.",
    "We hypothesize that {adj_l} priors yield substantial gains for {domain}.",
    "Crucially, our framework subsumes several existing approaches as special cases.",
    "We bridge a gap between theoretical guarantees and practical {domain} pipelines.",
    "Our motivation stems from observed instabilities in baseline systems.",
    "The contribution is threefold: we propose, analyze, and empirically validate the method.",
    "We demonstrate that the proposed approach generalizes across diverse {domain} regimes.",
    "Existing methods scale poorly; we address this directly.",
]

METHODS_SENTENCES = [
    "We train on a held-out split of {domain} data with {n} samples per class.",
    "The model is optimized using AdamW with cosine schedule over {epochs} epochs.",
    "Hyperparameters were selected via Bayesian optimization on a validation set.",
    "All experiments use single-precision arithmetic on {gpus}× A100 GPUs.",
    "We employ early stopping with patience {patience} on validation loss.",
    "Data augmentation includes random crops, color jitter, and Mixup.",
    "Following {cite}, we adopt a contrastive pretraining stage prior to fine-tuning.",
    "Our objective combines a reconstruction term with a KL divergence regularizer.",
    "We ablate each architectural component to isolate its contribution.",
    "Implementation uses PyTorch 2.3 with `torch.compile` for kernel fusion.",
    "Gradient clipping is applied at L2 norm {clip}.",
    "We use a batch size of {bs} with gradient accumulation across {accum} steps.",
]

RESULTS_SENTENCES = [
    "We achieve {pct}% relative improvement over the strongest baseline.",
    "The proposed method dominates the Pareto frontier of accuracy vs. compute.",
    "Statistical significance is confirmed via a paired t-test (p < 0.0{p}).",
    "Notably, performance scales log-linearly with model parameters in our regime.",
    "Calibration improves substantially, with expected calibration error reduced to {ece}%.",
    "Robustness under distribution shift improves by {shift}% over {cite}.",
    "We observe a phase transition near training step {step}k consistent with theory.",
    "Inference latency drops by {lat}% relative to a comparable transformer baseline.",
    "Memory footprint is reduced by {mem}× without sacrificing accuracy.",
    "Qualitative analysis reveals that learned representations cluster by class.",
    "Failure modes are concentrated on a small subset of OOD inputs.",
    "Convergence is monotone after step {step}k in all 5 random seeds.",
]


def _fill(template: str, seed: random.Random, ctx: dict) -> str:
    return template.format(
        adj_l=ctx["adj_l"],
        noun_l=ctx["noun_l"],
        domain=ctx["domain"],
        cite=seed.choice(CITATIONS),
        n=seed.choice([1_000, 5_000, 10_000, 50_000, 250_000]),
        epochs=seed.choice([20, 50, 100, 200, 500]),
        gpus=seed.choice([1, 2, 4, 8, 16, 32]),
        patience=seed.randint(3, 20),
        clip=round(seed.uniform(0.5, 5.0), 2),
        bs=seed.choice([32, 64, 128, 256, 512, 1024]),
        accum=seed.choice([1, 2, 4, 8]),
        pct=seed.randint(2, 47),
        p=seed.randint(1, 9),
        ece=round(seed.uniform(0.5, 4.5), 2),
        shift=seed.randint(5, 30),
        step=seed.randint(1, 50),
        lat=seed.randint(10, 70),
        mem=round(seed.uniform(1.5, 8.0), 1),
    )


def _section(templates: list[str], seed: random.Random, ctx: dict, n: int) -> str:
    paragraphs = []
    for _ in range(max(1, n // 6)):
        chunk = [seed.choice(templates) for _ in range(6)]
        paragraphs.append(" ".join(_fill(t, seed, ctx) for t in chunk))
    return "\n\n".join(paragraphs)


def _generate_paper() -> Paper:
    seed = random.Random(uuid.uuid4().hex)
    adj = seed.choice(ADJECTIVES)
    noun = seed.choice(NOUNS)
    domain = seed.choice(DOMAINS)
    nonce = uuid.uuid4().hex[:6]
    ctx = {"adj_l": adj.lower(), "noun_l": noun.lower(), "domain": domain}
    references = "\n".join(f"- {c}" for c in seed.sample(CITATIONS, k=6))
    return Paper(
        title=f"{adj} {noun} for {domain.title()} [{nonce}]",
        introduction=_section(INTRO_SENTENCES, seed, ctx, n=60),
        methods=_section(METHODS_SENTENCES, seed, ctx, n=72),
        results=_section(RESULTS_SENTENCES, seed, ctx, n=72),
        references=references,
        appendix="",
        tags=["stress-test", adj.lower(), noun.lower().split()[0], nonce],
    )


def _publish_one(client: CloudClient, i: int) -> tuple[int, str | None, str | None]:
    try:
        paper = _generate_paper()
        paper.id = _short_id(paper.title + datetime.now().isoformat() + str(i))
        payload = {
            "title": paper.title,
            "introduction": paper.introduction,
            "methods": paper.methods,
            "results": paper.results,
            "references": paper.references,
            "appendix": paper.appendix,
            "tags": paper.tags,
            "author_agent": "stress_test",
        }
        result = client.publish_paper(payload)
        return i, result.get("id"), None
    except Exception as e:
        return i, None, str(e)


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    p = int(sys.argv[2]) if len(sys.argv) > 2 else 16

    client = CloudClient()
    me = client.me()
    print(f"stress test: N={n} P={p} team={me['team_id']} email={me['email']}")

    t0 = time.time()
    ok = 0
    fail = 0
    with ThreadPoolExecutor(max_workers=p) as ex:
        futures = [ex.submit(_publish_one, client, i) for i in range(1, n + 1)]
        for fut in as_completed(futures):
            i, paper_id, err = fut.result()
            if err:
                fail += 1
                print(f"[{i}] FAIL: {err}")
            else:
                ok += 1
                if ok % 25 == 0 or ok == n:
                    elapsed = time.time() - t0
                    print(f"[{i}] ok ({ok}/{n}) {paper_id}  rate={ok/elapsed:.1f}/s")

    elapsed = time.time() - t0
    print(f"\ndone: {ok} published, {fail} failed in {elapsed:.1f}s ({ok/elapsed:.1f}/s)")


if __name__ == "__main__":
    main()
