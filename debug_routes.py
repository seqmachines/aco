import sys
from aco.api.main import create_app
from fastapi.routing import APIRoute

app = create_app()

for route in app.routes:
    if isinstance(route, APIRoute):
        print(f"{route.methods} {route.path}")
