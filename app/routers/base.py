from fastapi import APIRouter
from typing import List


class BaseRouter:
    def __init__(self, prefix: str, tags: List[str]):
        self.router = APIRouter(prefix=prefix, tags=tags)

    def get_router(self) -> APIRouter:
        return self.router
