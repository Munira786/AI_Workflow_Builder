from fastapi import APIRouter

from app.config import get_settings
from app.engine.registry import catalog
from app.schemas import NodeCatalogOut

router = APIRouter(prefix="/node-types", tags=["node types"])


@router.get("", response_model=NodeCatalogOut)
def list_node_types() -> dict:
    """Every node type the editor can place, with its handles, naming rule and whether it runs."""
    settings = get_settings()
    return catalog(settings.llm_model, settings.allowed_models)
