from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from app.models.user import Token, RefreshTokenRequest, UserPublic, UserInDB
from app.dependencies.auth import get_auth_service, get_current_user
from app.services.core.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/token", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(), auth_service: AuthService = Depends(get_auth_service)
):
    try:
        return await auth_service.login(form_data.username, form_data.password)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post("/refresh", response_model=Token)
async def refresh_token(refresh_request: RefreshTokenRequest, auth_service: AuthService = Depends(get_auth_service)):
    try:
        return await auth_service.refresh_access_token(refresh_request.refresh_token)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    current_user: UserInDB = Depends(get_current_user), auth_service: AuthService = Depends(get_auth_service)
):
    try:
        # Clear refresh token from user
        user_update = {"refresh_token": None, "refresh_token_expires": None}
        await auth_service.user_repository.update(current_user.id, user_update)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error during logout",
        )


@router.get("/me", response_model=UserPublic)
async def read_users_me(current_user: UserInDB = Depends(get_current_user)):
    return current_user


@router.get("/verify", status_code=status.HTTP_200_OK)
async def verify_token(current_user: UserInDB = Depends(get_current_user)):
    return {"status": "valid", "user_id": str(current_user.id)}
