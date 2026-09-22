from fastapi import APIRouter, Depends, status

from app.auth import require_admin
from app.database import supabase
from app.schemas import OrganizationCreate, OrganizationOut
from app.services import create_organization

router = APIRouter(prefix="/api/v1/organizations", tags=["Organizations"])

@router.post("", response_model=OrganizationOut, status_code=status.HTTP_201_CREATED)
def create_org(org: OrganizationCreate, payload: dict = Depends(require_admin)): # noqa: B008
    org_data = {
        "name": org.name,
        "identifier": org.identifier,
        "description": org.description,
        "status": "active"
    }
    return create_organization(supabase, org_data)