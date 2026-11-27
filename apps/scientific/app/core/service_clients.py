from typing import Any
from uuid import UUID

import httpx

from apps.scientific.app.core.config import settings


class ServiceContractError(RuntimeError):
    """Error al consumir un contrato HTTP interno."""


class _InternalServiceClient:
    def __init__(self, base_url: str):
        token = settings.internal_service_token
        if token is None or not token.get_secret_value():
            raise ServiceContractError("La credencial de servicio interno no está configurada.")
        self.base_url = base_url.rstrip("/")
        self.headers = {"X-Internal-Token": token.get_secret_value()}

    def get(
        self, path: str, *, params: dict[str, str] | None = None
    ) -> httpx.Response | None:
        try:
            with httpx.Client(timeout=15.0) as client:
                response = client.get(
                    f"{self.base_url}{path}",
                    headers=self.headers,
                    params=params,
                )
        except httpx.HTTPError as exc:
            raise ServiceContractError("No se pudo contactar el servicio interno.") from exc

        if response.status_code == 404:
            return None
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ServiceContractError(
                f"El servicio interno respondió HTTP {response.status_code}."
            ) from exc
        return response


class CoreServiceClient(_InternalServiceClient):
    def __init__(self):
        super().__init__(settings.core_api_url)

    def get_current_user_profile(
        self, user_id: UUID, email: str | None
    ) -> dict[str, Any]:
        response = self.get(
            f"/internal/v1/users/{user_id}/profile",
            params={"email": email} if email is not None else None,
        )
        if response is None:
            raise ServiceContractError("El perfil solicitado no fue encontrado.")
        return response.json()

    def get_organization_membership(
        self, user_id: UUID, organization_id: UUID
    ) -> dict[str, Any] | None:
        response = self.get(
            f"/internal/v1/organizations/{organization_id}/memberships/{user_id}"
        )
        return response.json() if response is not None else None

    def has_active_organization_membership(
        self, user_id: UUID, organization_id: UUID
    ) -> bool:
        return self.get_organization_membership(user_id, organization_id) is not None

    def get_dataset_version_for_training(
        self, version_id: UUID | str, organization_id: UUID | str
    ) -> dict[str, Any] | None:
        response = self.get(
            f"/internal/v1/datasets/versions/{version_id}",
            params={"organization_id": str(organization_id)},
        )
        return response.json() if response is not None else None

    def download_training_file(
        self,
        version_id: UUID | str,
        organization_id: UUID | str,
        user_id: UUID | str,
    ) -> tuple[bytes, str]:
        response = self.get(
            f"/internal/v1/datasets/versions/{version_id}/training-file/download",
            params={
                "organization_id": str(organization_id),
                "user_id": str(user_id),
            },
        )
        if response is None:
            raise ServiceContractError("El archivo de entrenamiento no fue encontrado.")
        checksum = response.headers.get("X-Training-Checksum")
        if not checksum:
            raise ServiceContractError("La respuesta Core no incluye checksum.")
        return response.content, checksum

    def get_dataset_provenance(
        self, version_id: UUID | str, organization_id: UUID | str
    ) -> dict[str, Any] | None:
        response = self.get(
            f"/internal/v1/datasets/versions/{version_id}/provenance",
            params={"organization_id": str(organization_id)},
        )
        return response.json() if response is not None else None


class SatelliteServiceClient(_InternalServiceClient):
    def __init__(self):
        super().__init__(settings.satellite_api_url)

    def get_scene_metadata(self, scene_id: UUID) -> dict[str, Any] | None:
        response = self.get(f"/internal/v1/scenes/{scene_id}")
        return response.json() if response is not None else None
