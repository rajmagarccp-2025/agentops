"""Domain enumeration and fundamental classification contracts."""

from enum import StrEnum


class CloudProvider(StrEnum):
    AWS = "aws"
    AZURE = "azure"
    GCP = "gcp"
    KUBERNETES = "kubernetes"
    OPENSHIFT = "openshift"
    GITHUB = "github"
    ON_PREM = "on-prem"


class Environment(StrEnum):
    LOCAL = "local"
    CI_TEST = "ci-test"
    STAGING = "staging"
    PRODUCTION = "production"


class StatementClassification(StrEnum):
    OBSERVED = "observed"
    INFERRED = "inferred"
    RECOMMENDED = "recommended"


class WorkflowStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"
    AWAITING_APPROVAL = "awaiting_approval"


class ResourceCategory(StrEnum):
    COMPUTE = "compute"
    STORAGE = "storage"
    DATABASE = "database"
    NETWORKING = "networking"
    SECURITY = "security"
    OBSERVABILITY = "observability"
    AI_MODEL = "ai-model"


class IncidentSeverity(StrEnum):
    SEV_1 = "sev-1"
    SEV_2 = "sev-2"
    SEV_3 = "sev-3"
    SEV_4 = "sev-4"
