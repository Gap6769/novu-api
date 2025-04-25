from app.routers.base import BaseRouter


class HealthRouter(BaseRouter):
    def __init__(self):
        super().__init__(prefix="/health", tags=["health"])
        self._setup_routes()

    def _setup_routes(self):
        @self.router.get("")
        async def health_check():
            return {"status": "ok"}


router = HealthRouter().get_router()
