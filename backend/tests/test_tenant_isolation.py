import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from platform_api.database import Base
from platform_api.identity_repository import (
    ProjectRepository,
    TenantRepository,
)
from platform_api.incidents.models import IncidentRecordModel
from platform_api.inventory.models import InventoryResourceRecord, ServiceModel


@pytest.fixture
def db_session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_table_all = Base.metadata.create_all
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_tenant_isolation_projects(db_session: Session):
    tenant_repo = TenantRepository()
    project_repo = ProjectRepository()

    t1 = tenant_repo.create_tenant(db_session, "Tenant 1", "tenant-1")
    t2 = tenant_repo.create_tenant(db_session, "Tenant 2", "tenant-2")

    project_repo.create_project(db_session, t1.id, "Proj T1", "proj-t1")
    project_repo.create_project(db_session, t2.id, "Proj T2", "proj-t2")

    t1_projects = project_repo.list_projects(db_session, t1.id)
    t2_projects = project_repo.list_projects(db_session, t2.id)

    assert len(t1_projects) == 1
    assert t1_projects[0].name == "Proj T1"

    assert len(t2_projects) == 1
    assert t2_projects[0].name == "Proj T2"

    assert project_repo.get_project_by_slug(db_session, t1.id, "proj-t2") is None


def test_tenant_isolation_services_and_resources(db_session: Session):
    t1_id = "tenant-alpha"
    t2_id = "tenant-beta"

    s1 = ServiceModel(tenant_id=t1_id, name="checkout-service")
    s2 = ServiceModel(tenant_id=t2_id, name="payment-service")
    db_session.add_all([s1, s2])

    r1 = InventoryResourceRecord(
        tenant_id=t1_id,
        resource_id="arn:aws:ec2:us-east-1:111:instance/i-1",
        provider="aws",
        kind="compute",
        name="k8s-node-1",
        region="us-east-1",
        environment="production",
        status="running",
    )
    r2 = InventoryResourceRecord(
        tenant_id=t2_id,
        resource_id="arn:aws:ec2:us-east-1:222:instance/i-2",
        provider="aws",
        kind="compute",
        name="k8s-node-2",
        region="us-east-1",
        environment="production",
        status="running",
    )
    db_session.add_all([r1, r2])
    db_session.commit()

    from sqlalchemy import select

    t1_resources = db_session.scalars(
        select(InventoryResourceRecord).where(InventoryResourceRecord.tenant_id == t1_id)
    ).all()
    assert len(t1_resources) == 1
    assert t1_resources[0].name == "k8s-node-1"


def test_tenant_isolation_incidents(db_session: Session):
    from datetime import UTC, datetime

    t1_id = "tenant-alpha"
    t2_id = "tenant-beta"

    inc1 = IncidentRecordModel(
        tenant_id=t1_id,
        title="High Error Rate",
        service="checkout",
        severity="sev-1",
        status="open",
        started_at=datetime.now(UTC),
    )
    inc2 = IncidentRecordModel(
        tenant_id=t2_id,
        title="Database Latency",
        service="payment",
        severity="sev-2",
        status="open",
        started_at=datetime.now(UTC),
    )
    db_session.add_all([inc1, inc2])
    db_session.commit()

    from sqlalchemy import select

    t1_incidents = db_session.scalars(
        select(IncidentRecordModel).where(IncidentRecordModel.tenant_id == t1_id)
    ).all()
    assert len(t1_incidents) == 1
    assert t1_incidents[0].title == "High Error Rate"
