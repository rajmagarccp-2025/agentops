from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import Float, cast, select
from sqlalchemy.orm import Session

from platform_api.database import SessionLocal, engine
from platform_api.rag_service.embedding import cosine_similarity
from platform_api.rag_service.models import (
    DocumentChunkModel,
    DocumentRecordModel,
    DocumentShareModel,
)
from platform_api.rag_service.schemas import (
    DocumentChunk,
    DocumentRecord,
    DocumentShareRecord,
    DocumentType,
)


def _check_stale(created_at: datetime, stale_after_days: int | None) -> bool:
    if not stale_after_days:
        return False
    now = datetime.now(UTC)
    return (now - created_at) > timedelta(days=stale_after_days)


class InMemoryRagRepository:
    def __init__(self) -> None:
        self.documents: dict[str, DocumentRecord] = {}
        self.chunks: dict[str, DocumentChunk] = {}
        self.shares: dict[str, list[DocumentShareRecord]] = {}

    def save_document(
        self,
        document: DocumentRecord,
        chunks: Iterable[DocumentChunk],
    ) -> DocumentRecord:
        self.documents[document.id] = document
        for chunk in chunks:
            self.chunks[chunk.id] = chunk
        return document

    def get_document(self, tenant_id: str, document_id: str) -> DocumentRecord | None:
        document = self.documents.get(document_id)
        return document if document and document.tenant_id == tenant_id else None

    def create_share(
        self,
        tenant_id: str,
        document_id: str,
        target_project_id: str,
        target_environment_id: str | None = None,
        shared_by: str | None = None,
    ) -> DocumentShareRecord:
        document = self.get_document(tenant_id, document_id)
        if not document:
            raise KeyError(f"Document {document_id} not found in tenant {tenant_id}")
        share = DocumentShareRecord(
            id=str(uuid4()),
            document_id=document_id,
            tenant_id=tenant_id,
            target_project_id=target_project_id,
            target_environment_id=target_environment_id,
            shared_by=shared_by,
            created_at=datetime.now(UTC),
        )
        self.shares.setdefault(document_id, []).append(share)
        return share

    def list_shares(self, tenant_id: str, document_id: str) -> list[DocumentShareRecord]:
        document = self.get_document(tenant_id, document_id)
        if not document:
            return []
        return [s for s in self.shares.get(document_id, []) if s.tenant_id == tenant_id]

    def revoke_share(self, tenant_id: str, document_id: str, share_id: str) -> bool:
        shares = self.shares.get(document_id, [])
        initial_len = len(shares)
        self.shares[document_id] = [
            s for s in shares if not (s.id == share_id and s.tenant_id == tenant_id)
        ]
        return len(self.shares[document_id]) < initial_len

    def list_documents(
        self,
        tenant_id: str,
        project_id: str | None = None,
        environment_id: str | None = None,
    ) -> list[DocumentRecord]:
        docs = []
        for doc in self.documents.values():
            if doc.tenant_id != tenant_id:
                continue
            is_unassigned = doc.project_id is None
            is_direct = (
                doc.project_id == project_id
                and (doc.environment_id is None or doc.environment_id == environment_id)
            )
            is_shared = any(
                s.target_project_id == project_id
                and (s.target_environment_id is None or s.target_environment_id == environment_id)
                for s in self.shares.get(doc.id, [])
                if s.tenant_id == tenant_id
            )
            if project_id is None or is_unassigned or is_direct or is_shared:
                docs.append(
                    doc.model_copy(
                        update={"is_stale": _check_stale(doc.created_at, doc.stale_after_days)}
                    )
                )
        return sorted(docs, key=lambda document: document.created_at, reverse=True)

    def accessible_chunks(
        self,
        tenant_id: str,
        roles: frozenset[str],
        document_type: DocumentType | None = None,
        service: str | None = None,
        environment: str | None = None,
        project_id: str | None = None,
        environment_id: str | None = None,
        tags: list[str] | None = None,
        include_stale: bool = True,
    ) -> list[DocumentChunk]:
        accessible_documents: dict[str, DocumentRecord] = {}
        for doc in self.documents.values():
            if doc.tenant_id != tenant_id:
                continue
            if project_id is None:
                if doc.project_id is not None:
                    continue
            else:
                is_direct = (
                    doc.project_id == project_id
                    and (doc.environment_id is None or doc.environment_id == environment_id)
                )
                is_shared = any(
                    s.target_project_id == project_id
                    and (
                        s.target_environment_id is None
                        or s.target_environment_id == environment_id
                    )
                    for s in self.shares.get(doc.id, [])
                    if s.tenant_id == tenant_id
                )
                if not is_direct and not is_shared:
                    continue
            doc_roles = {r.lower() for r in doc.allowed_roles}
            user_roles = {r.lower() for r in roles}
            if (
                doc.allowed_roles
                and "platform-admin" not in user_roles
                and "admin" not in user_roles
                and "owner" not in user_roles
                and not bool(doc_roles.intersection(user_roles))
            ):
                continue
            if document_type and doc.document_type != document_type:
                continue
            if service and doc.service != service:
                continue
            if environment and doc.environment != environment:
                continue
            if tags and not set(tags).issubset(set(doc.tags)):
                continue
            is_stale = _check_stale(doc.created_at, doc.stale_after_days)
            if is_stale and not include_stale:
                continue
            accessible_documents[doc.id] = doc

        return [
            chunk for chunk in self.chunks.values() if chunk.document_id in accessible_documents
        ]

    def search_similar_chunks(
        self,
        query_embedding: list[float],
        tenant_id: str,
        roles: frozenset[str],
        limit: int,
        document_type: DocumentType | None = None,
        service: str | None = None,
        environment: str | None = None,
        project_id: str | None = None,
        environment_id: str | None = None,
        tags: list[str] | None = None,
        include_stale: bool = True,
    ) -> list[tuple[float, DocumentChunk]]:
        chunks = self.accessible_chunks(
            tenant_id,
            roles,
            document_type,
            service,
            environment,
            project_id,
            environment_id,
            tags,
            include_stale,
        )
        return sorted(
            ((cosine_similarity(query_embedding, chunk.embedding), chunk) for chunk in chunks),
            key=lambda item: item[0],
            reverse=True,
        )[:limit]

    def update_document_scope(
        self,
        tenant_id: str,
        document_id: str,
        project_id: str,
        environment_id: str | None,
    ) -> DocumentRecord | None:
        document = self.get_document(tenant_id, document_id)
        if not document or (document.project_id is not None and document.project_id != project_id):
            return None
        updated = document.model_copy(
            update={"project_id": project_id, "environment_id": environment_id}
        )
        self.documents[document_id] = updated
        return updated

    def delete_document(
        self,
        tenant_id: str,
        document_id: str,
        project_id: str,
        environment_id: str,
        session: Session | None = None,
    ) -> bool:
        document = self.get_document(tenant_id, document_id)
        if not document or (
            document.project_id is not None
            and (
                document.project_id != project_id
                or (
                    document.environment_id is not None
                    and document.environment_id != environment_id
                )
            )
        ):
            return False
        del self.documents[document_id]
        for chunk_id in [
            chunk_id
            for chunk_id, chunk in self.chunks.items()
            if chunk.document_id == document_id and chunk.tenant_id == tenant_id
        ]:
            del self.chunks[chunk_id]
        return True

    @staticmethod
    def new_id() -> str:
        return str(uuid4())


class SqlAlchemyRagRepository(InMemoryRagRepository):
    def save_document(
        self,
        document: DocumentRecord,
        chunks: Iterable[DocumentChunk],
    ) -> DocumentRecord:
        with SessionLocal() as session:
            session.add(
                DocumentRecordModel(
                    id=document.id,
                    tenant_id=document.tenant_id,
                    project_id=document.project_id,
                    environment_id=document.environment_id,
                    source=document.source,
                    title=document.title,
                    document_type=document.document_type.value,
                    version=document.version,
                    service=document.service,
                    environment=document.environment,
                    tags=document.tags,
                    allowed_roles=document.allowed_roles,
                    stale_after_days=document.stale_after_days,
                    created_at=document.created_at,
                    updated_at=document.updated_at,
                )
            )
            session.add_all(
                [
                    DocumentChunkModel(
                        id=chunk.id,
                        document_id=chunk.document_id,
                        tenant_id=chunk.tenant_id,
                        ordinal=chunk.ordinal,
                        content=chunk.content,
                        metadata_json=chunk.metadata,
                        embedding=chunk.embedding,
                        embedding_provider=chunk.embedding_provider,
                        embedding_model=chunk.embedding_model,
                        embedding_version=chunk.embedding_version,
                        embedding_dimensions=chunk.embedding_dimensions,
                    )
                    for chunk in chunks
                ]
            )
            session.commit()
        return document

    def create_share(
        self,
        tenant_id: str,
        document_id: str,
        target_project_id: str,
        target_environment_id: str | None = None,
        shared_by: str | None = None,
    ) -> DocumentShareRecord:
        document = self.get_document(tenant_id, document_id)
        if not document:
            raise KeyError(f"Document {document_id} not found in tenant {tenant_id}")
        model = DocumentShareModel(
            document_id=document_id,
            tenant_id=tenant_id,
            target_project_id=target_project_id,
            target_environment_id=target_environment_id,
            shared_by=shared_by,
        )
        with SessionLocal() as session:
            session.add(model)
            session.commit()
            session.refresh(model)
            return _to_share(model)

    def list_shares(self, tenant_id: str, document_id: str) -> list[DocumentShareRecord]:
        with SessionLocal() as session:
            models = session.scalars(
                select(DocumentShareModel)
                .where(
                    DocumentShareModel.tenant_id == tenant_id,
                    DocumentShareModel.document_id == document_id,
                )
                .order_by(DocumentShareModel.created_at.desc())
            ).all()
            return [_to_share(m) for m in models]

    def revoke_share(self, tenant_id: str, document_id: str, share_id: str) -> bool:
        with SessionLocal() as session:
            model = session.scalar(
                select(DocumentShareModel).where(
                    DocumentShareModel.id == share_id,
                    DocumentShareModel.document_id == document_id,
                    DocumentShareModel.tenant_id == tenant_id,
                )
            )
            if not model:
                return False
            session.delete(model)
            session.commit()
            return True

    def get_document(self, tenant_id: str, document_id: str) -> DocumentRecord | None:
        with SessionLocal() as session:
            model = session.scalar(
                select(DocumentRecordModel).where(
                    DocumentRecordModel.tenant_id == tenant_id,
                    DocumentRecordModel.id == document_id,
                )
            )
            return _to_document(model) if model else None

    def list_documents(
        self,
        tenant_id: str,
        project_id: str | None = None,
        environment_id: str | None = None,
    ) -> list[DocumentRecord]:
        with SessionLocal() as session:
            models = session.scalars(
                select(DocumentRecordModel)
                .where(DocumentRecordModel.tenant_id == tenant_id)
                .order_by(DocumentRecordModel.created_at.desc())
            ).all()
            documents = [_to_document(model) for model in models]

            # Fetch active shares for this target scope within tenant
            shared_doc_ids: set[str] = set()
            if project_id is not None:
                share_stmt = select(DocumentShareModel.document_id).where(
                    DocumentShareModel.tenant_id == tenant_id,
                    DocumentShareModel.target_project_id == project_id,
                )
                if environment_id is not None:
                    share_stmt = share_stmt.where(
                        (DocumentShareModel.target_environment_id.is_(None))
                        | (DocumentShareModel.target_environment_id == environment_id)
                    )
                else:
                    share_stmt = share_stmt.where(
                        DocumentShareModel.target_environment_id.is_(None)
                    )
                shared_doc_ids = set(session.scalars(share_stmt).all())

            return [
                document
                for document in documents
                if project_id is None
                or document.project_id is None
                or (
                    document.project_id == project_id
                    and (
                        document.environment_id is None or document.environment_id == environment_id
                    )
                )
                or document.id in shared_doc_ids
            ]

    def accessible_chunks(
        self,
        tenant_id: str,
        roles: frozenset[str],
        document_type: DocumentType | None = None,
        service: str | None = None,
        environment: str | None = None,
        project_id: str | None = None,
        environment_id: str | None = None,
        tags: list[str] | None = None,
        include_stale: bool = True,
    ) -> list[DocumentChunk]:
        allowed_ids = self._accessible_document_ids(
            tenant_id,
            roles,
            document_type,
            service,
            environment,
            project_id,
            environment_id,
            tags,
            include_stale,
        )

        if not allowed_ids:
            return []
        with SessionLocal() as session:
            models = session.scalars(
                select(DocumentChunkModel).where(
                    DocumentChunkModel.tenant_id == tenant_id,
                    DocumentChunkModel.document_id.in_(allowed_ids),
                    DocumentChunkModel.embedding.is_not(None),
                )
            ).all()
            return [_to_chunk(model) for model in models]

    def search_similar_chunks(
        self,
        query_embedding: list[float],
        tenant_id: str,
        roles: frozenset[str],
        limit: int,
        document_type: DocumentType | None = None,
        service: str | None = None,
        environment: str | None = None,
        project_id: str | None = None,
        environment_id: str | None = None,
        tags: list[str] | None = None,
        include_stale: bool = True,
    ) -> list[tuple[float, DocumentChunk]]:
        allowed_ids = self._accessible_document_ids(
            tenant_id,
            roles,
            document_type,
            service,
            environment,
            project_id,
            environment_id,
            tags,
            include_stale,
        )
        if not allowed_ids:
            return []
        if engine.dialect.name != "postgresql":
            chunks = self.accessible_chunks(
                tenant_id,
                roles,
                document_type,
                service,
                environment,
                project_id,
                environment_id,
                tags,
                include_stale,
            )
            return sorted(
                (
                    (cosine_similarity(query_embedding, chunk.embedding), chunk)
                    for chunk in chunks
                ),
                key=lambda item: item[0],
                reverse=True,
            )[:limit]

        with SessionLocal() as session:
            distance = DocumentChunkModel.embedding.cosine_distance(query_embedding)
            similarity = cast(1.0 - distance, Float)
            rows = session.execute(
                select(DocumentChunkModel, similarity.label("score"))
                .where(
                    DocumentChunkModel.tenant_id == tenant_id,
                    DocumentChunkModel.document_id.in_(allowed_ids),
                    DocumentChunkModel.embedding.is_not(None),
                )
                .order_by(distance)
                .limit(limit)
            ).all()
            return [(float(score), _to_chunk(model)) for model, score in rows]

    def _accessible_document_ids(
        self,
        tenant_id: str,
        roles: frozenset[str],
        document_type: DocumentType | None,
        service: str | None,
        environment: str | None,
        project_id: str | None,
        environment_id: str | None,
        tags: list[str] | None,
        include_stale: bool,
    ) -> set[str]:
        documents = self.list_documents(tenant_id, project_id, environment_id)
        allowed_ids: set[str] = set()
        user_roles = {role.lower() for role in roles}
        for doc in documents:
            doc_roles = {role.lower() for role in doc.allowed_roles}
            if (
                doc.allowed_roles
                and "platform-admin" not in user_roles
                and "admin" not in user_roles
                and "owner" not in user_roles
                and not doc_roles.intersection(user_roles)
            ):
                continue
            if document_type and doc.document_type != document_type:
                continue
            if service and doc.service != service:
                continue
            if environment and doc.environment != environment:
                continue
            if tags and not set(tags).issubset(set(doc.tags)):
                continue
            if doc.is_stale and not include_stale:
                continue
            allowed_ids.add(doc.id)
        return allowed_ids

    def update_document_scope(
        self,
        tenant_id: str,
        document_id: str,
        project_id: str,
        environment_id: str | None,
    ) -> DocumentRecord | None:
        with SessionLocal() as session:
            model = session.scalar(
                select(DocumentRecordModel).where(
                    DocumentRecordModel.tenant_id == tenant_id,
                    DocumentRecordModel.id == document_id,
                )
            )
            if not model or (model.project_id is not None and model.project_id != project_id):
                return None
            model.project_id = project_id
            model.environment_id = environment_id
            session.commit()
            session.refresh(model)
            return _to_document(model)

    def delete_document(
        self,
        tenant_id: str,
        document_id: str,
        project_id: str,
        environment_id: str,
        session: Session | None = None,
    ) -> bool:
        def delete_in_session(active_session: Session) -> bool:
            model = active_session.scalar(
                select(DocumentRecordModel).where(
                    DocumentRecordModel.tenant_id == tenant_id,
                    DocumentRecordModel.id == document_id,
                )
            )
            if not model or (
                model.project_id is not None
                and (
                    model.project_id != project_id
                    or (model.environment_id is not None and model.environment_id != environment_id)
                )
            ):
                return False
            active_session.query(DocumentChunkModel).filter_by(
                tenant_id=tenant_id, document_id=document_id
            ).delete(synchronize_session=False)
            active_session.query(DocumentShareModel).filter_by(
                tenant_id=tenant_id, document_id=document_id
            ).delete(synchronize_session=False)
            active_session.delete(model)
            if session is None:
                active_session.commit()
            return True

        if session is not None:
            return delete_in_session(session)
        with SessionLocal() as active_session:
            return delete_in_session(active_session)


def _to_document(model: DocumentRecordModel) -> DocumentRecord:
    is_stale = _check_stale(model.created_at, model.stale_after_days)
    return DocumentRecord(
        id=model.id,
        tenant_id=model.tenant_id,
        project_id=model.project_id,
        environment_id=model.environment_id,
        scope=(
            "unassigned"
            if model.project_id is None
            else "project"
            if model.environment_id is None
            else "environment"
        ),
        source=model.source,
        title=model.title,
        document_type=DocumentType(model.document_type),
        version=model.version,
        service=model.service,
        environment=model.environment,
        tags=model.tags,
        allowed_roles=model.allowed_roles,
        stale_after_days=model.stale_after_days,
        is_stale=is_stale,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _to_chunk(model: DocumentChunkModel) -> DocumentChunk:
    if model.embedding is None:
        raise ValueError(f"Document chunk {model.id} has no active embedding")
    return DocumentChunk(
        id=model.id,
        document_id=model.document_id,
        tenant_id=model.tenant_id,
        ordinal=model.ordinal,
        content=model.content,
        metadata=model.metadata_json,
        embedding=model.embedding,
        embedding_provider=model.embedding_provider,
        embedding_model=model.embedding_model,
        embedding_version=model.embedding_version,
        embedding_dimensions=model.embedding_dimensions,
    )


def _to_share(model: DocumentShareModel) -> DocumentShareRecord:
    return DocumentShareRecord(
        id=model.id,
        document_id=model.document_id,
        tenant_id=model.tenant_id,
        target_project_id=model.target_project_id,
        target_environment_id=model.target_environment_id,
        shared_by=model.shared_by,
        created_at=model.created_at,
    )
