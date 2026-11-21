"""FastAPI application factory."""

from fastapi import FastAPI

from habits.api import schemas
from habits.api.errors import install_error_handlers
from habits.api.routes import habits
from habits.api.settings import Settings
from habits.storage.db import make_engine, make_session_factory


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the app; never runs migrations."""
    settings = settings or Settings.from_env()
    app = FastAPI(title="Habit Tracker API", version="1.0.0")
    engine = make_engine(settings.database_url)
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = make_session_factory(engine)
    install_error_handlers(app)
    app.include_router(habits.router)

    @app.get("/health", operation_id="health")
    def health() -> schemas.Health:
        return schemas.Health()

    return app


app = create_app()
