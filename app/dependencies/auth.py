from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from app.repositories.user_repository import UserRepository
from app.db.database import get_database
from app.services.core.auth_service import AuthService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")


def get_user_repository(db=Depends(get_database)) -> UserRepository:
    return UserRepository(db)


def get_auth_service(user_repository: UserRepository = Depends(get_user_repository)) -> AuthService:
    return AuthService(user_repository)


async def get_current_user(token: str = Depends(oauth2_scheme), auth_service: AuthService = Depends(get_auth_service)):
    try:
        return await auth_service.get_current_user(token)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )
