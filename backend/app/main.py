from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import os

from .api import auth, matters, documents, sources, jobs, ai_endpoint, corpus, search, matter_ws, citation, procedure, research, audit_export, drafting, firm, plan, authority, similarity, pipeline
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
app.include_router(pipeline.router)

# Minimal browseable web frontend (single self-contained page).
_static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")


@app.get("/ui", response_class=HTMLResponse)
def web_ui():
    with open(os.path.join(_static_dir, "index.html"), encoding="utf-8") as fh:
        return HTMLResponse(fh.read())


@app.get("/frontend", response_class=HTMLResponse)
def frontend_alias():
    with open(os.path.join(_static_dir, "index.html"), encoding="utf-8") as fh:
        return HTMLResponse(fh.read())


@app.get("/health", tags=["system"])
def health():
    return {"status": "ok", "env": settings.app_env, "debug": settings.debug}


@app.get("/", response_class=HTMLResponse)
def root():
    version = app.version
    env = settings.app_env
    return """<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>NOMOS — Cyprus Legal Intelligence Platform</title>
<style>
:root{{color-scheme:light dark}} body{{font-family:system-ui,sans-serif;max-width:760px;margin:2.5rem auto;padding:0 1.2rem;line-height:1.55}}
h1{{font-size:2rem;margin-bottom:.15rem}} header p.tag{{color:#6b7280;margin:.2rem 0 1rem}}
a{{color:#1d4ed8}} ul{{line-height:1.9}} footer{{color:#9ca3af;font-size:.85rem;margin-top:1.5rem}}
</style>
</head><body>
<header><h1>NOMOS</h1><p class="tag">Evidence-first legal research &amp; matter-intelligence</p></header>
<main>
<p>This is the NOMOS API. Browse the API documentation or key workflow endpoints below.</p>
<ul>
<li><a href="/ui">Web UI (login → search)</a></li>
<li><a href="/docs">Interactive API docs (Swagger UI)</a></li>
<li><a href="/health">Health check</a></li>
<li><a href="/openapi.json">OpenAPI specification</a></li>
<li><a href="/sources/registry">Source registry</a></li>
<li><a href="/search?q=insolvency">Search (needs auth)</a></li>
</ul>
</main>
<footer><span>NOMOS {version}</span> · <span>env: {env}</span></footer>
</body></html>""".format(version=version, env=env)