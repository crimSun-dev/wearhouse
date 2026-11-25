"""Wearhouse v2 canonical API.

Layering (enforced by tests/test_boundaries.py):
    api (FastAPI routers) -> application services -> domain rules / ports
    adapters (SQL, OIDC, crypto) implement ports and are composed only in `bootstrap`.
Domain/application/ports modules import neither FastAPI nor SQLAlchemy, and nothing imports the
legacy v1 runtime under legacy/.
"""

__version__ = "0.1.0"
