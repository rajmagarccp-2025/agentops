from __future__ import annotations

from types import SimpleNamespace

import pytest
from google.api_core.exceptions import GoogleAPIError, NotFound
from google.cloud import secretmanager

from platform_api.secrets.providers import adapters


class FakeSecretManagerClient:
    def __init__(self) -> None:
        self.secrets: dict[str, dict[str, object]] = {}
        self.access_requests: list[str] = []
        self.fail_add_version = False

    def create_secret(self, request: dict[str, object]) -> SimpleNamespace:
        parent = str(request["parent"])
        secret_id = str(request["secret_id"])
        name = f"{parent}/secrets/{secret_id}"
        if name in self.secrets:
            from google.api_core.exceptions import AlreadyExists

            raise AlreadyExists("already exists")
        secret = request["secret"]
        labels = secret["labels"]  # type: ignore[index]
        self.secrets[name] = {"labels": labels, "versions": []}
        return SimpleNamespace(name=name)

    def get_secret(self, request: dict[str, str]) -> SimpleNamespace:
        secret = self.secrets.get(request["name"])
        if secret is None:
            raise NotFound("missing")
        return SimpleNamespace(name=request["name"], labels=secret["labels"])

    def add_secret_version(self, request: dict[str, object]) -> SimpleNamespace:
        if self.fail_add_version:
            raise GoogleAPIError("confidential-payload-must-not-escape")
        parent = str(request["parent"])
        secret = self.secrets.get(parent)
        if secret is None:
            raise NotFound("missing")
        versions = secret["versions"]
        version_num = len(versions) + 1  # type: ignore[arg-type]
        name = f"{parent}/versions/{version_num}"
        payload = request["payload"]
        data = payload["data"]  # type: ignore[index]
        versions.append(  # type: ignore[union-attr]
            {
                "name": name,
                "data": data,
                "state": secretmanager.SecretVersion.State.ENABLED,
            }
        )
        return SimpleNamespace(name=name)

    def access_secret_version(self, request: dict[str, str]) -> SimpleNamespace:
        name = request["name"]
        self.access_requests.append(name)
        secret_name, version_label = name.rsplit("/versions/", 1)
        secret = self.secrets.get(secret_name)
        if secret is None:
            raise NotFound("missing")
        versions = secret["versions"]
        version = (
            versions[-1]  # type: ignore[index]
            if version_label == "latest"
            else next(
                (item for item in versions if item["name"] == name),  # type: ignore[union-attr]
                None,
            )
        )
        if version is None or version["state"] != secretmanager.SecretVersion.State.ENABLED:
            raise NotFound("missing or disabled")
        return SimpleNamespace(payload=SimpleNamespace(data=version["data"]))

    def get_secret_version(self, request: dict[str, str]) -> SimpleNamespace:
        name = request["name"]
        secret_name = name.rsplit("/versions/", 1)[0]
        secret = self.secrets.get(secret_name)
        if secret is None:
            raise NotFound("missing")
        version = next(
            (item for item in secret["versions"] if item["name"] == name),  # type: ignore[union-attr]
            None,
        )
        if version is None:
            raise NotFound("missing")
        return SimpleNamespace(name=name, state=version["state"])

    def disable_secret_version(self, request: dict[str, str]) -> None:
        self._set_state(request["name"], secretmanager.SecretVersion.State.DISABLED)

    def enable_secret_version(self, request: dict[str, str]) -> None:
        self._set_state(request["name"], secretmanager.SecretVersion.State.ENABLED)

    def _set_state(self, name: str, state: int) -> None:
        secret_name = name.rsplit("/versions/", 1)[0]
        secret = self.secrets.get(secret_name)
        if secret is None:
            raise NotFound("missing")
        version = next(
            (item for item in secret["versions"] if item["name"] == name),  # type: ignore[union-attr]
            None,
        )
        if version is None:
            raise NotFound("missing")
        version["state"] = state

    def list_secret_versions(self, request: dict[str, str]) -> list[SimpleNamespace]:
        secret = self.secrets.get(request["parent"])
        if secret is None:
            raise NotFound("missing")
        return [
            SimpleNamespace(name=item["name"], state=item["state"])
            for item in secret["versions"]  # type: ignore[union-attr]
        ]


def _adapter(
    monkeypatch: pytest.MonkeyPatch,
    tenant_id: str = "tenant-alpha",
    client: FakeSecretManagerClient | None = None,
) -> adapters.GCPSecretManagerAdapter:
    monkeypatch.setattr(
        adapters,
        "get_settings",
        lambda: SimpleNamespace(
            app_env="production",
            gcp_secret_manager_project_id="agentops-prod-123",
        ),
    )
    provider = SimpleNamespace(
        provider_type="gcp_secret_manager",
        tenant_id=tenant_id,
        vault_identifier="agentops-prod-123",
        endpoint_url=None,
        auth_method="workload_identity",
        credentials_config_encrypted=None,
    )
    return adapters.GCPSecretManagerAdapter(provider, client=client)


def test_gcp_adapter_creates_versions_reads_and_manages_version_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = FakeSecretManagerClient()
    adapter = _adapter(monkeypatch, client=client)

    version_one, encrypted, metadata = adapter.create_secret(
        "DATABASE_PASSWORD", "synthetic-secret-value"
    )
    assert version_one and version_one.endswith("/versions/1")
    assert encrypted is None
    assert metadata == {"provider": "gcp_secret_manager"}
    assert adapter.read_secret_value("DATABASE_PASSWORD", version_one) == "synthetic-secret-value"

    version_two, _, _ = adapter.update_secret_value("DATABASE_PASSWORD", "rotated-value")
    assert version_two and version_two.endswith("/versions/2")
    assert adapter.read_secret_value("DATABASE_PASSWORD", version_two) == "rotated-value"

    assert adapter.set_secret_version_enabled("DATABASE_PASSWORD", version_two, enabled=False)
    with pytest.raises(RuntimeError, match="access failed"):
        adapter.read_secret_value("DATABASE_PASSWORD", version_two)
    assert adapter.set_secret_version_enabled("DATABASE_PASSWORD", version_two, enabled=True)
    assert adapter.read_secret_value("DATABASE_PASSWORD", version_two) == "rotated-value"

    assert adapter.delete_secret("DATABASE_PASSWORD")
    with pytest.raises(RuntimeError, match="access failed"):
        adapter.read_secret_value("DATABASE_PASSWORD")


def test_gcp_create_is_idempotent_for_retries_and_rejects_replacement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = FakeSecretManagerClient()
    adapter = _adapter(monkeypatch, client=client)
    original_ref, _, _ = adapter.create_secret("RETRY_SECRET", "same-value")

    retry_ref, _, _ = adapter.create_secret("RETRY_SECRET", "same-value")
    assert retry_ref == original_ref
    with pytest.raises(RuntimeError, match="different active value"):
        adapter.create_secret("RETRY_SECRET", "different-value")


def test_gcp_adapter_scopes_names_by_tenant_and_rejects_foreign_refs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = FakeSecretManagerClient()
    tenant_a = _adapter(monkeypatch, "tenant-a", client)
    tenant_b = _adapter(monkeypatch, "tenant-b", client)

    ref_a, _, _ = tenant_a.create_secret("SHARED_NAME", "alpha")
    ref_b, _, _ = tenant_b.create_secret("SHARED_NAME", "beta")

    assert ref_a != ref_b
    assert tenant_a.read_secret_value("SHARED_NAME", ref_a) == "alpha"
    assert tenant_b.read_secret_value("SHARED_NAME", ref_b) == "beta"
    with pytest.raises(ValueError, match="version reference"):
        tenant_b.read_secret_value("SHARED_NAME", ref_a)


def test_gcp_connection_test_uses_real_api_and_redacts_secret_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = FakeSecretManagerClient()
    adapter = _adapter(monkeypatch, client=client)
    probe_name = f"projects/agentops-prod-123/secrets/{adapter._PROBE_SECRET_ID}"
    client.secrets[probe_name] = {
        "labels": {},
        "versions": [
            {
                "name": f"{probe_name}/versions/1",
                "data": b"probe-value",
                "state": secretmanager.SecretVersion.State.ENABLED,
            }
        ],
    }

    result = adapter.test_connection()
    assert result.success
    assert client.access_requests == [f"{probe_name}/versions/latest"]
    assert "probe-value" not in result.message

    client.fail_add_version = True
    with pytest.raises(RuntimeError) as exc:
        adapter.update_secret_value("DATABASE_PASSWORD", "confidential-payload-must-not-escape")
    assert "confidential-payload-must-not-escape" not in str(exc.value)
    assert exc.value.__cause__ is None


def test_gcp_adapter_requires_trusted_project_and_workload_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        adapters,
        "get_settings",
        lambda: SimpleNamespace(
            app_env="production",
            gcp_secret_manager_project_id="agentops-prod-123",
        ),
    )
    invalid_provider = SimpleNamespace(
        provider_type="gcp_secret_manager",
        tenant_id="tenant",
        vault_identifier="attacker-project",
        endpoint_url="https://attacker.example",
        auth_method="service_account_key",
        credentials_config_encrypted="encrypted-key",
    )

    with pytest.raises(ValueError, match="configured project and Workload Identity"):
        adapters.GCPSecretManagerAdapter(invalid_provider, client=FakeSecretManagerClient())
