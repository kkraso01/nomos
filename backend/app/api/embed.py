from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException

from ..core.tenancy import require_org
from ..services.embedding import get_provider, cosine

router = APIRouter(prefix="/ai", tags=["embeddings"])


class EmbedIn(BaseModel):
    texts: list[str]
    is_query: bool = False


@router.post("/embed")
def embed_texts(payload: EmbedIn, ctx: dict = Depends(require_org)):
    prov = get_provider()
    if not prov.available():
        raise HTTPException(503, "No embedding provider configured")
    vectors = prov.embed(payload.texts, is_query=payload.is_query)
    return {"meta": prov.meta(), "vectors": vectors}


class SimIn(BaseModel):
    a: list[float]
    b: list[float]


@router.post("/cosine")
def cosine_sim(payload: SimIn, ctx: dict = Depends(require_org)):
    return {"similarity": round(cosine(payload.a, payload.b), 4)}