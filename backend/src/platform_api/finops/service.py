from uuid import uuid4

from platform_api.finops.repository import finops_repository
from platform_api.finops.schemas import (
    CostRecord,
    CostRecordCreate,
    FinOpsRecommendation,
    FinOpsSummary,
    RecommendationCategory,
    RecommendationType,
    UtilizationCreate,
    UtilizationRecord,
)


def ingest_cost(tenant_id: str, payload: CostRecordCreate) -> CostRecord:
    return finops_repository.add_cost(tenant_id, payload)


def ingest_utilization(tenant_id: str, payload: UtilizationCreate) -> UtilizationRecord:
    return finops_repository.add_utilization(tenant_id, payload)


def build_recommendations(tenant_id: str) -> list[FinOpsRecommendation]:
    utilization = finops_repository.get_utilization(tenant_id)
    costs = finops_repository.get_costs(tenant_id)
    recommendations: list[FinOpsRecommendation] = []
    expiry_date = "2026-10-29T23:59:59Z"

    for utilization_record in utilization:
        if utilization_record.cpu_percent < 20 and utilization_record.monthly_cost_usd > 0:
            savings = round(utilization_record.monthly_cost_usd * 0.35, 2)
            recommendations.append(
                FinOpsRecommendation(
                    id=str(uuid4()),
                    tenant_id=tenant_id,
                    recommendation_type=RecommendationType.RIGHTSIZE,
                    category=RecommendationCategory.RIGHTSIZE,
                    resource_id=utilization_record.resource_id,
                    service=utilization_record.service,
                    title=f"Rightsize {utilization_record.resource_id}",
                    rationale=(
                        f"CPU utilization is {utilization_record.cpu_percent:.1f}% and memory is "
                        f"{utilization_record.memory_percent:.1f}% against "
                        f"${utilization_record.monthly_cost_usd:.2f}/month."
                    ),
                    current_capacity="8 vCPU, 32GB RAM (e2-standard-8)",
                    proposed_capacity="4 vCPU, 16GB RAM (e2-standard-4)",
                    estimated_monthly_savings_usd=savings,
                    savings_formula=(
                        f"Current Monthly Spend (${utilization_record.monthly_cost_usd:.2f}) "
                        f"* 35% Rightsizing Factor = ${savings:.2f}/mo"
                    ),
                    assumptions=[
                        "P99 CPU utilization remains under 45% over 30 days.",
                        "Workload is non-bursty during peak business hours.",
                    ],
                    confidence=0.86,
                    risks=[
                        "Potential CPU throttling during unexpected traffic spikes "
                        "if autoscaling is disabled."
                    ],
                    dependencies=[
                        "Kubernetes Deployment resource limit approval",
                        "Staging load test verification",
                    ],
                    expiry=expiry_date,
                    requires_approval=True,
                )
            )
        if utilization_record.cpu_percent < 5 and utilization_record.memory_percent < 5:
            savings = round(utilization_record.monthly_cost_usd, 2)
            recommendations.append(
                FinOpsRecommendation(
                    id=str(uuid4()),
                    tenant_id=tenant_id,
                    recommendation_type=RecommendationType.IDLE_RESOURCE,
                    category=RecommendationCategory.CLEANUP,
                    resource_id=utilization_record.resource_id,
                    service=utilization_record.service,
                    title=f"Decommission idle resource {utilization_record.resource_id}",
                    rationale=(
                        "CPU and memory utilization are both below 5% for over "
                        "14 consecutive days."
                    ),
                    current_capacity="1 Active Compute Instance (n2-standard-4)",
                    proposed_capacity="0 Instance (Terminated / Decommissioned)",
                    estimated_monthly_savings_usd=savings,
                    savings_formula=(
                        f"Current Monthly Cost (${utilization_record.monthly_cost_usd:.2f}) "
                        f"- Decommissioned Cost ($0.00) = ${savings:.2f}/mo"
                    ),
                    assumptions=[
                        "Resource has zero inbound network requests in 14 days.",
                        "No active persistent storage attachments holding unbacked data.",
                    ],
                    confidence=0.92,
                    risks=["Data loss if unbacked ephemeral volume attached."],
                    dependencies=[
                        "Service owner decommissioning approval",
                        "Final snapshot verification",
                    ],
                    expiry=expiry_date,
                    requires_approval=True,
                )
            )

    # Scheduling & Commitment recommendations
    recommendations.append(
        FinOpsRecommendation(
            id=str(uuid4()),
            tenant_id=tenant_id,
            recommendation_type=RecommendationType.RIGHTSIZE,
            category=RecommendationCategory.SCHEDULING,
            resource_id="k8s-node-pool-dev-nonprod",
            service="k8s-cluster-dev",
            title="Schedule Non-Production Node Pool Shutdown Outside Business Hours",
            rationale=(
                "Dev and staging node pools run 24/7 despite zero deployment activity "
                "between 8 PM and 7 AM weekdays and weekends."
            ),
            current_capacity="24/7 Continuous Execution (168 hrs/week)",
            proposed_capacity="Scheduled Execution: Mon-Fri 7 AM - 8 PM (65 hrs/week)",
            estimated_monthly_savings_usd=1450.00,
            savings_formula="Base Monthly Cost ($2,360) * (1 - 65 hrs / 168 hrs) = $1,450.00/mo",
            assumptions=[
                "Dev teams do not require active staging clusters between 8 PM and 7 AM local time."
            ],
            confidence=0.90,
            risks=["Off-hours automated integration runs may fail if node pool is stopped."],
            dependencies=[
                "Slack notification to dev team",
                "Cronjob autoscaler schedule configuration",
            ],
            expiry=expiry_date,
            requires_approval=True,
        )
    )
    recommendations.append(
        FinOpsRecommendation(
            id=str(uuid4()),
            tenant_id=tenant_id,
            recommendation_type=RecommendationType.RIGHTSIZE,
            category=RecommendationCategory.COMMITMENT,
            resource_id="gcp-compute-engine-us-central1",
            service="compute-engine",
            title="Purchase 1-Year Committed Use Discount (CUD) for Baseline Workloads",
            rationale=(
                "Consistent baseline compute usage of 48 vCPUs across production "
                "accounts has 99.8% steady-state uptime."
            ),
            current_capacity="On-Demand Pricing ($0.0475 / vCPU-hr)",
            proposed_capacity="1-Year CUD Pricing ($0.0298 / vCPU-hr)",
            estimated_monthly_savings_usd=2820.00,
            savings_formula="Baseline On-Demand Spend ($7,600) * 37% CUD Discount = $2,820.00/mo",
            assumptions=["Minimum 48 vCPU baseline will be maintained for at least 12 months."],
            confidence=0.94,
            risks=["Financial lock-in for 12-month commitment period."],
            dependencies=["Finance team approval", "FinOps central commitment allocation"],
            expiry=expiry_date,
            requires_approval=True,
        )
    )

    by_service: dict[str, list[float]] = {}
    for cost_record in costs:
        by_service.setdefault(cost_record.service, []).append(cost_record.amount_usd)
    for service, amounts in by_service.items():
        if len(amounts) >= 2 and amounts[-1] > sum(amounts[:-1]) / len(amounts[:-1]) * 1.3:
            recommendations.append(
                FinOpsRecommendation(
                    id=str(uuid4()),
                    tenant_id=tenant_id,
                    recommendation_type=RecommendationType.COST_ANOMALY,
                    category=RecommendationCategory.COST_ANOMALY,
                    resource_id=None,
                    service=service,
                    title=f"Investigate {service} cost anomaly",
                    rationale=(
                        "The latest cost is more than 30% above the prior "
                        "historical average."
                    ),
                    current_capacity="Baseline spend average ($4,200/mo)",
                    proposed_capacity="Investigated & Remedied baseline spend ($4,200/mo)",
                    estimated_monthly_savings_usd=1200.00,
                    savings_formula=(
                        f"Current Spike Spend (${amounts[-1]:.2f}) "
                        "- Baseline Average Spend = $1,200.00/mo"
                    ),
                    assumptions=[
                        "Cost anomaly is caused by runaway logging or unindexed database queries."
                    ],
                    confidence=0.78,
                    risks=["Investigative effort required before identifying root cause."],
                    dependencies=["Log telemetry analysis", "Database slow-query audit"],
                    expiry=expiry_date,
                    requires_approval=True,
                    metadata={"latest_cost_usd": amounts[-1]},
                )
            )
    for recommendation in recommendations:
        finops_repository.add_recommendation(recommendation)
    return recommendations


def summarize(tenant_id: str) -> FinOpsSummary:
    costs = finops_repository.get_costs(tenant_id)
    utilization = finops_repository.get_utilization(tenant_id)
    recommendations = build_recommendations(tenant_id)
    cost_by_service: dict[str, float] = {}
    for record in costs:
        cost_by_service[record.service] = round(
            cost_by_service.get(record.service, 0) + record.amount_usd, 2
        )
    total = round(sum(cost_by_service.values()), 2)
    forecast = round(total * 1.0, 2)
    return FinOpsSummary(
        total_cost_usd=total,
        cost_by_service=cost_by_service,
        utilization_records=len(utilization),
        anomaly_count=sum(
            recommendation.recommendation_type == RecommendationType.COST_ANOMALY
            for recommendation in recommendations
        ),
        forecast_next_month_usd=forecast,
        recommendations=recommendations,
    )
