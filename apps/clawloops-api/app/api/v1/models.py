from fastapi import APIRouter, Depends

from app.core.auth import AuthContext
from app.core.dependencies import get_app_settings, get_auth_context, require_active_user
from app.infra.model_gateway_client import ModelGatewayClient
from app.schemas.models import ModelItem, ModelListResponse


router = APIRouter(tags=["models"], dependencies=[Depends(require_active_user)])


@router.get("/models", response_model=ModelListResponse)
async def list_models(
    ctx: AuthContext = Depends(get_auth_context),
    settings=Depends(get_app_settings),
) -> ModelListResponse:
    model_base_url = settings.model_gateway_base_url or "http://litellm:4000"
    preferred_models = settings.get_model_gateway_default_models()

    client = ModelGatewayClient(model_base_url)
    payload = client.get_user_model_config(user_id=ctx.userId, preferred_models=preferred_models)
    models = payload.get("models", []) if isinstance(payload, dict) else []
    if not isinstance(models, list):
        models = []

    return ModelListResponse(
        models=[
            ModelItem(
                modelId=model_id,
                name=model_id,
                provider="litellm",
                source="gateway",
                enabled=True,
                defaultRoute=f"litellm/{model_id}",
            )
            for model_id in models
        ]
    )
