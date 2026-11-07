from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Security, status

from apps.api.app.core.auth import verify_supabase_jwt
from apps.api.app.core.database import supabase
from apps.api.app.core.dependencies import require_admin
from apps.api.app.domains.identity.schemas_identity import (
    DashboardSummaryResponse,
    MembershipCreate,
    OrganizationCreate,
    OrganizationMemberResponse,
    OrganizationOut,
    ProfileOption,
    UserOrganizationResponse,
)
from apps.api.app.domains.identity.service_identity import (
    add_organization_member,
    create_organization_with_admin,
    get_all_profiles_service,
    get_dashboard_summary,
    get_organization_members_for_user,
    get_user_organizations_service,
)

router = APIRouter()

organizations_router = APIRouter(prefix="/api/v1/organizations", tags=["Organizations"])
dashboard_router = APIRouter(prefix="/api/v1/dashboard", tags=["Dashboard"])


# --- Endpoints de Organizations ---


@organizations_router.get("/profiles", response_model=list[ProfileOption])
def list_profiles_for_members(payload: dict = Depends(require_admin)):  # noqa: B008
    return get_all_profiles_service(supabase)


@organizations_router.get("/", response_model=list[UserOrganizationResponse])
def get_user_organizations(payload: dict = Depends(verify_supabase_jwt)):  # noqa: B008
    """Recupera las organizaciones exclusivas del usuario autenticado."""
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identificador de usuario no encontrado en el token.",
        )

    try:
        return get_user_organizations_service(supabase, str(user_id))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error en el motor de base de datos al recuperar organizaciones: {exc}",
        ) from exc


@organizations_router.get(
    "/{organization_id}/members",
    response_model=list[OrganizationMemberResponse],
)
def list_organization_members(
    organization_id: UUID,
    payload: dict = Security(verify_supabase_jwt),  # noqa: B008
):
    if supabase is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El servicio de autenticación no está disponible",
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token sin identificador de usuario (sub).",
        )

    current_user_id = UUID(str(user_id))

    try:
        return get_organization_members_for_user(
            supabase, current_user_id, organization_id
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc


@organizations_router.post("/{id}/members")
def create_organization_member(
    id: UUID,
    membership: MembershipCreate,
    payload: dict = Depends(verify_supabase_jwt),  # noqa: B008
):
    try:
        return add_organization_member(
            supabase=supabase,
            org_id=id,
            profile_id=membership.profile_id,
            role=membership.role,
            requester_user_id=UUID(str(payload["sub"])),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@organizations_router.post(
    "", response_model=OrganizationOut, status_code=status.HTTP_201_CREATED
)
def create_org(
    org: OrganizationCreate,
    payload: dict = Depends(require_admin),  # noqa: B008
):
    org_data = {
        "name": org.name,
        "identifier": org.identifier,
        "description": org.description,
        "status": "active",
    }
    return create_organization_with_admin(supabase, org_data, str(payload["sub"]))


# --- Endpoints de Dashboard ---


@dashboard_router.get("/summary", response_model=DashboardSummaryResponse)
def dashboard_summary(payload: dict = Depends(verify_supabase_jwt)):  # noqa: B008
    if supabase is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El servicio de base de datos no está disponible",
        )
    return get_dashboard_summary(supabase, payload)


@dashboard_router.get("/profiles", response_model=list[ProfileOption])
def dashboard_profiles(payload: dict = Depends(verify_supabase_jwt)):  # noqa: B008
    if supabase is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El servicio de base de datos no está disponible",
        )
    try:
        return get_all_profiles_service(supabase)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener los perfiles: {exc!s}",
        ) from exc


router.include_router(organizations_router)
router.include_router(dashboard_router)
