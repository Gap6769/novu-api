from fastapi import APIRouter, Depends, HTTPException
from app.models.user import UserCreate, UserUpdate, UserPublic, UserInDB
from app.repositories.user_repository import UserRepository
from app.routers.auth.router import get_current_user, get_user_repository

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/register", response_model=UserPublic)
async def register(user: UserCreate, user_repository: UserRepository = Depends(get_user_repository)):
    db_user = await user_repository.get_by_email(user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    return await user_repository.create(user)


@router.get("/me", response_model=UserPublic)
async def read_users_me(current_user: UserInDB = Depends(get_current_user)):
    return current_user


@router.put("/me", response_model=UserPublic)
async def update_user_me(
    user_update: UserUpdate,
    current_user: UserInDB = Depends(get_current_user),
    user_repository: UserRepository = Depends(get_user_repository),
):
    return await user_repository.update(current_user.id, user_update)


@router.put("/me/preferences", response_model=UserPublic)
async def update_user_preferences(
    preferences: dict,
    current_user: UserInDB = Depends(get_current_user),
    user_repository: UserRepository = Depends(get_user_repository),
):
    return await user_repository.update_preferences(current_user.id, preferences)
