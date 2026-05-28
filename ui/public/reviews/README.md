# Review HTMLs

Each round of the hackathon, Society-of-Agents (`~/Documents/Code/Society-of-agents`)
runs review passes over the published papers and emits a compiled HTML report.

To publish a round's reviews:

1. Run reviews in Society-of-Agents and compile the report (see `scripts/compile_reviews.py` there).
2. Copy the resulting HTML file over the matching round placeholder in this directory:
   - `round-1.html`
   - `round-2.html`
   - `round-3.html`
3. Commit and push to `main`.
4. Run `infra/deploy-spa.sh` to deploy (the build copies `ui/public/*` into the SPA bundle and invalidates CloudFront).

The `/reviews` page in the SPA links to all three round HTMLs. Until a round is posted, its
placeholder displays a "not yet posted" message.

The HTML should be fully self-contained (inline CSS, no SPA dependencies) because these
files are served as static assets, not through React Router.
