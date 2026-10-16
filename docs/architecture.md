# Enterprise Platform Architecture

## Platform Overview

The Cloud-Agnostic Agentic SRE, FinOps & LLMOps Platform is an enterprise operations control plane for SRE, platform, cloud, security, FinOps, MLOps, and AI/LLMOps teams.

```text
                         ┌──────────────────────┐
                         │      End Users       │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │    Next.js Web UI    │
                         │   User Platform      │
                         └──────────┬───────────┘
                                    │
                              HTTPS / API
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │ API Gateway / FastAPI │
                         └──────────┬───────────┘
                                    │
                    ┌───────────────┼────────────────┐
                    │               │                │
                    ▼               ▼                ▼
             Authentication    Agent Platform    User/API
                    │               │                │
                    │               ▼                │
                    │       ┌───────────────┐        │
                    │       │ Agent Router  │        │
                    │       └───────┬───────┘        │
                    │               │                │
                    │      ┌────────┼────────┐       │
                    │      ▼        ▼        ▼       │
                    │    Agent    Agent    Agent     │
                    │      1        2        N        │
                    │                               │
                    └──────────────┬────────────────┘
                                   │
                                   ▼
                            MCP / Tool Layer
                                   │
                    ┌──────────────┼──────────────┐
                    ▼              ▼              ▼
                   AWS           Azure           GCP
                    │              │              │
                    └──────────────┼──────────────┘
                                   │
                                   ▼
                              Terraform
                                   │
                                   ▼
                             Cloud Resources
```

## Core Specialist Agents

1. **SRE Agent**: Reliability, P95 latency tracking, incident correlation, root cause analysis.
2. **DevOps / Change Agent**: Deployment risk calculation, git commit correlation, IAC drift detection.
3. **Security Agent**: Threat detection, IAM role assumption auditing, network CIDR enforcement.
4. **Cloud / Discovery Agent**: Multi-cloud asset inventory, topology mapping across AWS, Azure, GCP, K8s.
5. **FinOps Agent**: Spend forecasting, rightsizing recommendations, idle resource cleanup.
6. **MLOps Agent**: Pipeline health, training loss tracking, feature store drift evaluation.
7. **AI / LLMOps Agent**: Token telemetry, prompt performance, P99 latency tracking, cost management.
8. **Remediation Agent**: Policy check, human approval binding, allowlisted mutation execution.
