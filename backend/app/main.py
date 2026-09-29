from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import auth, matters, documents, sources, jobs, ai_endpoint, corpus, search, matter_ws, citation, procedure, research, audit_export, drafting, firm, plan, authority, similarity
from .config import settings

app = FastAPI(
    title="NOMOS API",
    version="0.1.0",
    description="Cyprus legal intelligence platform",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(matters.router)
app.include_router(documents.router)
app.include_router(sources.router)
app.include_router(jobs.router)
app.include_router(ai_endpoint.router)
app.include_router(corpus.router)
app.include_router(search.router)
app.include_router(matter_ws.router)
app.include_router(citation.router)
app.include_router(procedure.router)
app.include_router(research.router)
app.include_router(audit_export.router)
app.include_router(drafting.router)
app.include_router(firm.router)
app.include_router(plan.router)
app.include_router(authority.router)
app.include_router(authority.follow_router)
app.include_router(similarity.router)


@app.get("/health", tags=["system"])
def health():
    return {"status": "ok", "env": settings.app_env, "debug": settings.debug}


@app.get("/")
def root():
    return {"app": "NOMOS", "docs": "/docs"}