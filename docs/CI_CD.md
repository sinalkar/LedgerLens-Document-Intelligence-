# CI/CD Pipeline

Three workflows under `.github/workflows/`. No cloud deploy — the published Docker image is the deliverable and runs anywhere (`docker run`, Cloud Run, Render, Railway, a VM).

```
Pull request ──▶ ci.yml      lint · tests · security scan · docker build check
             └─▶ codeql.yml  SAST code scanning

Merge to main ─▶ ci.yml + codeql.yml (again, on the merged tree)
             └─▶ release.yml tests → GHCR image push → Trivy scan → GitHub Release
```

## `ci.yml` — quality gate (every PR and push to main)

| Job | What it does | Blocking? |
|---|---|---|
| `lint` | `ruff check .` — code quality/style errors | ✅ |
| `test` | `pytest tests/ -v` — 51 tests, fully offline via `FakeProvider` (no API keys) | ✅ |
| `security` | `bandit -r app -ll` (Python SAST, fails on medium+ severity) and `pip-audit` (dependency CVEs) | Bandit ✅ / pip-audit informational |
| `docker` | Builds the image without pushing — a broken Dockerfile fails the PR, with GitHub Actions layer caching | ✅ |

`pip-audit` is `continue-on-error` deliberately: a CVE published upstream in a pinned dependency shouldn't freeze all development, but it stays visible in every run's logs.

## `codeql.yml` — code scanning (PRs, main, weekly)

GitHub CodeQL with the `security-extended` query pack for Python. Findings appear under **Security → Code scanning** in the repo. The weekly Monday schedule re-scans unchanged code against newly published vulnerability patterns.

## `release.yml` — release on merge (push to main)

1. **Test gate** — the full pytest suite runs again on the merged tree; a red suite blocks the release.
2. **Version** — `v0.1.<run_number>`, monotonically increasing, no manual tagging needed.
3. **Docker publish** — image pushed to GitHub Container Registry as:
   - `ghcr.io/<owner>/<repo>:latest`
   - `ghcr.io/<owner>/<repo>:v0.1.N`
   - `ghcr.io/<owner>/<repo>:sha-<commit>`
4. **Trivy image scan** — CRITICAL/HIGH container vulnerabilities uploaded as SARIF to code scanning (informational).
5. **GitHub Release** — created with the version tag, auto-generated release notes (the commit/PR list since the previous release), and pull/run instructions for the published image.

Authentication uses the built-in `GITHUB_TOKEN` — no secrets to configure.

## Running the release image

```bash
docker pull ghcr.io/<owner>/<repo>:latest
docker run --env-file .env -p 8080:8080 ghcr.io/<owner>/<repo>:latest
```

See [`.env.example`](../.env.example) for configuration. Note: the first published package may be private by default — make it public under the package's settings on GitHub if you want anonymous pulls.

## Local pre-flight

Reproduce the CI gate before pushing:

```bash
ruff check .
bandit -r app -ll
pytest tests/ -q
docker build -t ledgerlens .
```
