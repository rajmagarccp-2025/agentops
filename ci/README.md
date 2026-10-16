# CI/CD

The repository uses GitHub Actions for quality gates, image validation, and
deployment promotion. GitOps reconciliation remains owned by Argo CD.

## Workflows

- `github-actions/quality.yml`: backend lint/type/tests, frontend checks, manifest
	rendering, secret placeholder scanning, Gitleaks, and Trivy filesystem scanning
- `github-actions/containers.yml`: API/web image builds and Trivy image scans
- `github-actions/deploy.yml`: deployment validation on main
- `github-actions/release.yml`: environment promotion workflow with a production gate

Pull requests must pass code quality, tests, frontend build, Kubernetes rendering,
and security scans before promotion. Secrets are supplied through CI secret stores
or workload identity and are never committed to the repository.
