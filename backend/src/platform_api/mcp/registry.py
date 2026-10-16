import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from platform_api.contracts.domain import CloudProvider
from platform_api.database import SessionLocal
from platform_api.mcp.audit import AuditSink, create_audit_event
from platform_api.mcp.models import ToolIdempotencyRecord
from platform_api.mcp.redaction import sanitize_dict
from platform_api.mcp.types import ToolCategory, ToolHandler, ToolResult, ToolRisk
from platform_api.observability import increment, span
from platform_api.security import Principal


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    category: ToolCategory
    risk: ToolRisk
    required_permission: str
    input_model: type[BaseModel]
    handler: ToolHandler
    provider: CloudProvider = CloudProvider.GCP
    version: str = "1.0"
    timeout_ms: int = 30_000
    idempotent: bool = True


@dataclass(frozen=True)
class ToolExecution:
    execution_id: str
    status: str
    tool_name: str
    risk: ToolRisk
    tenant_id: str
    result: ToolResult | None = None
    validation_errors: list[dict[str, object]] | None = None


class ToolNotFoundError(KeyError):
    pass


class ToolAuthorizationError(PermissionError):
    pass


class ToolValidationError(ValueError):
    pass


class ToolExecutionInProgressError(RuntimeError):
    pass


class ToolRegistry:
    def __init__(self, tools: Iterable[ToolSpec], audit_sink: AuditSink) -> None:
        self._tools = {tool.name: tool for tool in tools}
        self._audit_sink = audit_sink

    @staticmethod
    def _request_hash(
        parameters: dict[str, object], principal: Principal
    ) -> str:
        canonical = json.dumps(
            {
                "parameters": parameters,
                "project_id": principal.project_id,
                "environment_id": principal.environment_id,
            },
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        return hashlib.sha256(canonical.encode()).hexdigest()

    @staticmethod
    def _from_idempotency_record(record: ToolIdempotencyRecord) -> ToolExecution:
        response = record.response_json or {}
        raw_result = response.get("result")
        result = ToolResult.model_validate(raw_result) if raw_result is not None else None
        return ToolExecution(
            execution_id=record.execution_id,
            status=str(response.get("status", record.status)),
            tool_name=record.tool_name,
            risk=ToolRisk(str(response.get("risk", ToolRisk.LOW_RISK.value))),
            tenant_id=record.tenant_id,
            result=result,
            validation_errors=response.get("validation_errors"),
        )

    def _reserve_idempotency(
        self,
        *,
        tenant_id: str,
        tool_name: str,
        idempotency_key: str,
        request_hash: str,
        execution_id: str,
    ) -> ToolExecution | None:
        if not 1 <= len(idempotency_key) <= 255:
            raise ToolValidationError("Idempotency key must contain between 1 and 255 characters")
        with SessionLocal() as db:
            existing = db.scalar(
                select(ToolIdempotencyRecord).where(
                    ToolIdempotencyRecord.tenant_id == tenant_id,
                    ToolIdempotencyRecord.tool_name == tool_name,
                    ToolIdempotencyRecord.idempotency_key == idempotency_key,
                )
            )
            if existing is not None:
                if existing.request_hash != request_hash:
                    raise ToolValidationError(
                        "Idempotency key was already used for a different tool request"
                    ) from None
                if existing.status == "processing":
                    raise ToolExecutionInProgressError(
                        "A tool execution with this idempotency key is already in progress"
                    ) from None
                return self._from_idempotency_record(existing)

            db.add(
                ToolIdempotencyRecord(
                    tenant_id=tenant_id,
                    tool_name=tool_name,
                    idempotency_key=idempotency_key,
                    request_hash=request_hash,
                    status="processing",
                    execution_id=execution_id,
                )
            )
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                existing = db.scalar(
                    select(ToolIdempotencyRecord).where(
                        ToolIdempotencyRecord.tenant_id == tenant_id,
                        ToolIdempotencyRecord.tool_name == tool_name,
                        ToolIdempotencyRecord.idempotency_key == idempotency_key,
                    )
                )
                if existing is None:
                    raise
                if existing.request_hash != request_hash:
                    raise ToolValidationError(
                        "Idempotency key was already used for a different tool request"
                    ) from None
                if existing.status == "processing":
                    raise ToolExecutionInProgressError(
                        "A tool execution with this idempotency key is already in progress"
                    ) from None
                return self._from_idempotency_record(existing)
        return None

    @staticmethod
    def _complete_idempotency(
        *,
        tenant_id: str,
        tool_name: str,
        idempotency_key: str | None,
        execution_id: str,
        status: str,
        risk: ToolRisk,
        result: ToolResult | None = None,
        error_summary: str | None = None,
    ) -> None:
        if idempotency_key is None:
            return
        with SessionLocal() as db:
            record = db.scalar(
                select(ToolIdempotencyRecord).where(
                    ToolIdempotencyRecord.tenant_id == tenant_id,
                    ToolIdempotencyRecord.tool_name == tool_name,
                    ToolIdempotencyRecord.idempotency_key == idempotency_key,
                    ToolIdempotencyRecord.execution_id == execution_id,
                )
            )
            if record is None:
                raise RuntimeError("Tool idempotency reservation disappeared during execution")
            if record.status != "processing":
                return
            record.status = status
            record.error_summary = error_summary
            record.response_json = {
                "status": status,
                "risk": risk.value,
                "result": result.model_dump(mode="json") if result is not None else None,
            }
            record.updated_at = datetime.now(UTC)
            db.commit()

    def list_tools(self) -> list[ToolSpec]:
        return sorted(self._tools.values(), key=lambda tool: tool.name)

    def get(self, name: str) -> ToolSpec:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise ToolNotFoundError(name) from exc

    def execute(
        self,
        name: str,
        parameters: dict[str, object],
        principal: Principal,
        request_id: str,
        dry_run: bool,
        approved: bool = False,
        idempotency_key: str | None = None,
        expected_provider: CloudProvider | None = None,
        expected_version: str | None = None,
    ) -> ToolExecution:
        tool = self.get(name)

        # Provider & Version Validation
        if expected_provider and tool.provider != expected_provider:
            raise ToolValidationError(
                f"Provider mismatch for {name}: expected {expected_provider.value}, "
                f"got {tool.provider.value}"
            )
        if expected_version and tool.version != expected_version:
            raise ToolValidationError(
                f"Version mismatch for {name}: expected {expected_version}, got {tool.version}"
            )

        # Principal & Tenant Authentication Revalidation
        if not principal.tenant_id:
            raise ToolAuthorizationError("Tenant ID is required for tool execution")

        # Application Permission Validation
        if (
            tool.required_permission not in principal.permissions
            and "platform:admin" not in principal.permissions
            and "platform-admin" not in principal.permissions
        ):
            raise ToolAuthorizationError(tool.required_permission)

        execution_id = str(uuid4())
        sanitized_params = sanitize_dict(parameters)

        # Input Schema Validation
        try:
            validated = tool.input_model.model_validate(parameters)
        except ValidationError as exc:
            errors = [dict(error) for error in exc.errors()]
            self._audit_sink.record(
                create_audit_event(
                    execution_id,
                    principal.tenant_id,
                    principal.subject,
                    name,
                    tool.risk,
                    sanitized_params,
                    "validation_failed",
                    request_id,
                    project_id=getattr(principal, "project_id", None),
                    environment_id=getattr(principal, "environment_id", None),
                    actor_email=getattr(principal, "email", None),
                )
            )
            exec_res = ToolExecution(
                execution_id=execution_id,
                status="validation_failed",
                tool_name=name,
                risk=tool.risk,
                tenant_id=principal.tenant_id,
                validation_errors=errors,
            )
            return exec_res

        if idempotency_key:
            previous = self._reserve_idempotency(
                tenant_id=principal.tenant_id,
                tool_name=name,
                idempotency_key=idempotency_key,
                request_hash=self._request_hash(parameters, principal),
                execution_id=execution_id,
            )
            if previous is not None:
                return previous

        # Risk Classification & Approval Integration Interface
        if tool.risk in {ToolRisk.HIGH_RISK, ToolRisk.CRITICAL} and not dry_run and not approved:
            outcome = "approval_required"
            self._audit_sink.record(
                create_audit_event(
                    execution_id,
                    principal.tenant_id,
                    principal.subject,
                    name,
                    tool.risk,
                    sanitized_params,
                    outcome,
                    request_id,
                    project_id=getattr(principal, "project_id", None),
                    environment_id=getattr(principal, "environment_id", None),
                    actor_email=getattr(principal, "email", None),
                )
            )
            exec_res = ToolExecution(
                execution_id=execution_id,
                status=outcome,
                tool_name=name,
                risk=tool.risk,
                tenant_id=principal.tenant_id,
            )
            self._complete_idempotency(
                tenant_id=principal.tenant_id,
                tool_name=name,
                idempotency_key=idempotency_key,
                execution_id=execution_id,
                status=outcome,
                risk=tool.risk,
            )
            return exec_res

        # Execution
        from time import perf_counter

        from platform_api.observability import record_tool_execution

        t_start = perf_counter()
        self._audit_sink.record(
            create_audit_event(
                execution_id,
                principal.tenant_id,
                principal.subject,
                name,
                tool.risk,
                sanitized_params,
                "started",
                request_id,
                project_id=getattr(principal, "project_id", None),
                environment_id=getattr(principal, "environment_id", None),
                actor_email=getattr(principal, "email", None),
            )
        )
        try:
            with span(
                "mcp.tool.call",
                {
                    "mcp.tool": name,
                    "mcp.risk": tool.risk.value,
                    "mcp.provider": tool.provider.value,
                    "tool_call_id": execution_id,
                    "request_id": request_id,
                    "tenant_id": principal.tenant_id,
                },
            ):
                raw_result = tool.handler(validated, principal.tenant_id)
        except Exception:
            try:
                self._audit_sink.record(
                    create_audit_event(
                        execution_id,
                        principal.tenant_id,
                        principal.subject,
                        name,
                        tool.risk,
                        sanitized_params,
                        "failed",
                        request_id,
                        project_id=getattr(principal, "project_id", None),
                        environment_id=getattr(principal, "environment_id", None),
                        actor_email=getattr(principal, "email", None),
                    )
                )
            finally:
                self._complete_idempotency(
                    tenant_id=principal.tenant_id,
                    tool_name=name,
                    idempotency_key=idempotency_key,
                    execution_id=execution_id,
                    status="failed",
                    risk=tool.risk,
                    error_summary="tool_handler_failed",
                )
            increment(f"mcp.tool.{name}.errors")
            raise

        dur_ms = (perf_counter() - t_start) * 1000
        # Response Normalization & Sensitive Value Redaction
        sanitized_data = sanitize_dict(raw_result.data) if raw_result and raw_result.data else {}
        normalized_result = ToolResult(status=raw_result.status, data=sanitized_data)

        increment("mcp.tool.executions")
        outcome = "dry_run" if dry_run else "executed"
        record_tool_execution(name, tool.risk.value, raw_result.status == "ok", dur_ms)

        self._audit_sink.record(
            create_audit_event(
                execution_id,
                principal.tenant_id,
                principal.subject,
                name,
                tool.risk,
                sanitized_params,
                outcome,
                request_id,
                project_id=getattr(principal, "project_id", None),
                environment_id=getattr(principal, "environment_id", None),
                actor_email=getattr(principal, "email", None),
            )
        )

        exec_res = ToolExecution(
            execution_id=execution_id,
            status=outcome,
            tool_name=name,
            risk=tool.risk,
            tenant_id=principal.tenant_id,
            result=normalized_result,
        )

        self._complete_idempotency(
            tenant_id=principal.tenant_id,
            tool_name=name,
            idempotency_key=idempotency_key,
            execution_id=execution_id,
            status=outcome,
            risk=tool.risk,
            result=normalized_result,
        )
        return exec_res
