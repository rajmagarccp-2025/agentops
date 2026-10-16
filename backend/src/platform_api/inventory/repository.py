from collections.abc import Iterable

from sqlalchemy import delete, select

from platform_api.database import SessionLocal
from platform_api.inventory.models import InventoryResourceRecord
from platform_api.inventory.schemas import InventoryResource, ResourceKind


class InventoryRepository:
    def replace_for_tenant(
        self,
        tenant_id: str,
        resources: Iterable[InventoryResource],
    ) -> list[InventoryResource]:
        raise NotImplementedError

    def list_for_tenant(self, tenant_id: str) -> list[InventoryResource]:
        raise NotImplementedError


class InMemoryInventoryRepository(InventoryRepository):
    def __init__(self) -> None:
        self._resources: dict[str, dict[str, InventoryResource]] = {}

    def replace_for_tenant(
        self,
        tenant_id: str,
        resources: Iterable[InventoryResource],
    ) -> list[InventoryResource]:
        normalized = {resource.resource_id: resource for resource in resources}
        self._resources[tenant_id] = normalized
        return list(normalized.values())

    def list_for_tenant(self, tenant_id: str) -> list[InventoryResource]:
        return sorted(
            self._resources.get(tenant_id, {}).values(),
            key=lambda resource: resource.resource_id,
        )


class SqlAlchemyInventoryRepository(InventoryRepository):
    def replace_for_tenant(
        self,
        tenant_id: str,
        resources: Iterable[InventoryResource],
    ) -> list[InventoryResource]:
        normalized = list({resource.resource_id: resource for resource in resources}.values())
        with SessionLocal() as session:
            session.execute(
                delete(InventoryResourceRecord).where(
                    InventoryResourceRecord.tenant_id == tenant_id
                )
            )
            session.add_all(
                [
                    InventoryResourceRecord(
                        tenant_id=tenant_id,
                        resource_id=resource.resource_id,
                        provider=resource.provider,
                        kind=resource.kind.value,
                        name=resource.name,
                        region=resource.region,
                        environment=resource.environment,
                        service=resource.service,
                        status=resource.status,
                        resource_metadata=resource.metadata,
                    )
                    for resource in normalized
                ]
            )
            session.commit()
        return normalized

    def list_for_tenant(self, tenant_id: str) -> list[InventoryResource]:
        with SessionLocal() as session:
            models = session.scalars(
                select(InventoryResourceRecord)
                .where(InventoryResourceRecord.tenant_id == tenant_id)
                .order_by(InventoryResourceRecord.resource_id)
            ).all()
            return [
                InventoryResource(
                    resource_id=model.resource_id,
                    provider=model.provider,
                    kind=ResourceKind(model.kind),
                    name=model.name,
                    region=model.region,
                    environment=model.environment,
                    service=model.service,
                    status=model.status,
                    metadata=model.resource_metadata,
                )
                for model in models
            ]
