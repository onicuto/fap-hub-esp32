import os
import json
from pathlib import Path
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(title="ESP32 FAP Catalog API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_dist_dir() -> Path:
    if "DIST_DIR" in os.environ:
        return Path(os.environ["DIST_DIR"])
    # Local development: server/app/../../dist -> fap-hub-esp32/dist
    repo_dist = Path(__file__).resolve().parent.parent.parent / "dist"
    if repo_dist.exists():
        return repo_dist
    # Docker container: /app/app/../dist -> /app/dist
    docker_dist = Path(__file__).resolve().parent.parent / "dist"
    if docker_dist.exists():
        return docker_dist
    return repo_dist

DIST_DIR = get_dist_dir()
CATALOG_FILE = DIST_DIR / "catalog.json"
BUILDS_DIR = DIST_DIR / "builds"
ICONS_DIR = DIST_DIR / "icons"

BUILDS_DIR.mkdir(parents=True, exist_ok=True)
ICONS_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/builds", StaticFiles(directory=str(BUILDS_DIR)), name="builds")
app.mount("/icons", StaticFiles(directory=str(ICONS_DIR)), name="icons")

def load_catalog_data():
    if not CATALOG_FILE.exists():
        return {"categories": [], "applications": []}
    with open(CATALOG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

class ApplicationsQuery(BaseModel):
    offset: Optional[int] = 0
    limit: Optional[int] = 50
    query: Optional[str] = None
    category_id: Optional[str] = None
    applications: Optional[List[str]] = None
    sort_by: Optional[str] = None
    sort_order: Optional[int] = None
    target: Optional[str] = None
    api: Optional[str] = None
    has_version: Optional[bool] = None
    is_latest_release_version: Optional[bool] = None

def format_app_for_client(app_meta: dict, base_url: str):
    app_id = app_meta["id"]
    version = app_meta.get("version", "1.0")
    icon_filename = app_meta.get("icon_file")
    icon_url = f"{base_url}/icons/{icon_filename}" if icon_filename else f"{base_url}/icons/default.png"
    fap_filename = app_meta.get("fap_file", f"{app_id}.fap")
    bundle_url = f"{base_url}/builds/{fap_filename}"

    return {
        "_id": app_id,
        "alias": app_id,
        "category_id": app_meta.get("category", "tools"),
        "created_at": 1700000000,
        "updated_at": 1700000000,
        "current_version": {
            "_id": f"ver_{app_id}_{version}",
            "name": app_meta.get("name", app_id),
            "version": version,
            "short_description": app_meta.get("description", ""),
            "icon_uri": icon_url,
            "screenshots": [],
            "status": "READY",
            "description": app_meta.get("description", ""),
            "changelog": "Initial release for ESP32",
            "links": {
                "bundle_uri": bundle_url,
                "manifest_uri": "",
                "source_code": {
                    "type": "APPLICATION_SOURCE_TYPE_DEFAULT",
                    "uri": ""
                }
            }
        }
    }

# Categories endpoints (support both /0/category and /api/v0/category)
@app.get("/0/category")
@app.get("/api/v0/category")
async def get_categories(request: Request, limit: Optional[int] = 100):
    catalog = load_catalog_data()
    cats = catalog.get("categories", [])
    base_url = str(request.base_url).rstrip("/")
    res = []
    for c in cats:
        cat_id = c["id"]
        count = sum(1 for a in catalog.get("applications", []) if a.get("category") == cat_id)
        res.append({
            "_id": cat_id,
            "priority": c.get("priority", 1),
            "name": c.get("name", cat_id.capitalize()),
            "color": c.get("color", "#4A90E2"),
            "icon_uri": f"{base_url}/icons/cat_{cat_id}.svg",
            "applications": count
        })
    return res

# Applications list endpoint (POST /1/application and /api/v0/application)
@app.post("/1/application")
@app.post("/api/v0/application")
async def list_applications(request: Request, query: ApplicationsQuery):
    catalog = load_catalog_data()
    apps = catalog.get("applications", [])
    base_url = str(request.base_url).rstrip("/")

    # Filtering
    if query.category_id:
        apps = [a for a in apps if a.get("category") == query.category_id]
    if query.query:
        q = query.query.lower()
        apps = [a for a in apps if q in a.get("name", "").lower() or q in a.get("id", "").lower() or q in a.get("description", "").lower()]
    if query.applications:
        app_set = set(query.applications)
        apps = [a for a in apps if a.get("id") in app_set]

    # Pagination
    offset = query.offset or 0
    limit = query.limit or 50
    paged = apps[offset:offset+limit]

    return [format_app_for_client(a, base_url) for a in paged]

# Featured applications
@app.get("/0/application/featured")
@app.get("/api/v0/application/featured")
async def get_featured(request: Request):
    catalog = load_catalog_data()
    apps = catalog.get("applications", [])
    base_url = str(request.base_url).rstrip("/")
    return [format_app_for_client(a, base_url) for a in apps[:5]]

# Application detail
@app.get("/0/application/{uid}")
@app.get("/api/v0/application/{uid}")
async def get_application(uid: str, request: Request):
    catalog = load_catalog_data()
    app_meta = next((a for a in catalog.get("applications", []) if a.get("id") == uid), None)
    if not app_meta:
        raise HTTPException(status_code=404, detail="Application not found")
    base_url = str(request.base_url).rstrip("/")
    return format_app_for_client(app_meta, base_url)

# Binary FAP download endpoint
@app.get("/0/application/version/{version_id}/build/compatible")
@app.get("/api/v0/application/version/{version_id}/build/compatible")
async def download_compatible_build(version_id: str):
    # version_id is like "ver_{app_id}_{version}"
    catalog = load_catalog_data()
    target_app = None
    for a in catalog.get("applications", []):
        app_id = a["id"]
        version = a.get("version", "1.0")
        if version_id == f"ver_{app_id}_{version}" or version_id == app_id:
            target_app = a
            break

    if not target_app:
        # Try finding by prefix
        for a in catalog.get("applications", []):
            if a["id"] in version_id:
                target_app = a
                break

    if not target_app:
        raise HTTPException(status_code=404, detail="Build not found")

    fap_path = BUILDS_DIR / target_app.get("fap_file", f"{target_app['id']}.fap")
    if not fap_path.exists():
        raise HTTPException(status_code=404, detail="FAP binary file not found on server")

    return FileResponse(
        path=str(fap_path),
        filename=fap_path.name,
        media_type="application/octet-stream"
    )

@app.get("/health")
def health():
    return {"status": "ok"}
