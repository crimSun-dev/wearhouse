> **Historical document.** Paths here predate the `legacy/` relocation; see `docs/architecture/migration-inventory.md` §3 for the current locations.

# Digital Wardrobe frontend

Integrated source: `Frontend/frontend/` in this repository. GitHub Pages builds
the landing page and `/app/` with the public Neon Function API URL. See
[`../docs/DEPLOYMENT.md`](../docs/DEPLOYMENT.md) for the live setup.

The Vite site contains the editorial forecast story at `/` and the wardrobe app at `/app/`. Copy `frontend/`, `PRODUCT.md`, and `DESIGN.md` into the existing Live Demo checkout.

## Development

1. From the Live Demo repository, start FastAPI with `.\run_demo.ps1 -Offline`. The app makes requests to the backend at port 8000 through Vite's same-origin proxy.
2. In `frontend/`, run `npm install` and then `npm run dev`.
3. Open `http://127.0.0.1:5173/`. Use `/app/#/demo` for the interface log and fault controls.

Optional build variables are `VITE_API_BASE`, `VITE_API_KEY`, and `VITE_AVATAR_MODELS=true`. The API base defaults to the same origin and the key defaults to the brief’s synthetic-user demo key. For drop-in GLBs, put the backend-named files under `frontend/public/models/` and enable the avatar models flag. The app otherwise uses procedural Three.js meshes and an illustrated fallback.

## Checks

- `npm test` runs the API and outfit composition tests without additional dependencies.
- `npm run typecheck` checks the handwritten API declarations.
- `npm run types:api` generates types after the existing repository's exported `docs/openapi.json` is present.
- `npm run test:e2e` uses Playwright and the running offline backend. Install the test browser with `npx playwright install chromium` after installing packages. Use an offline demo database when running it, as it changes fault state and issues an activation code.
- `npm run build` writes both HTML entries to `frontend/dist`.

## FastAPI static serving

In the existing `backend/app/main.py`, replace the plain index route inside `create_app()` with the following after every router, retaining the existing path and response imports. Restart FastAPI after building the frontend.

```python
from fastapi.staticfiles import StaticFiles

frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
else:
    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(STATIC_DIR / "index.html")
```

The landing timeline uses clearly labelled illustrative weather scenes. Hero weather reads the real backend if it is available. The planning app uses the documented API, with no seeded client data. FastAPI serves the built frontend when present, and GitHub Pages publishes it automatically on pushes to main.
