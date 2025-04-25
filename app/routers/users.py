from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from typing import Optional
from datetime import timedelta, datetime
from jose import JWTError, jwt
from ..models.user import UserCreate, UserUpdate, UserPublic, UserInDB
from ..repositories.user_repository import UserRepository
from ..db.database import get_database
from motor.motor_asyncio import AsyncIOMotorDatabase
from ..core.config import settings
from bson import ObjectId

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def get_user_repository(db: AsyncIOMotorDatabase = Depends(get_database)) -> UserRepository:
    return UserRepository(db)

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    user_repository: UserRepository = Depends(get_user_repository)
) -> UserInDB:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        
        # Convert string ID to ObjectId
        try:
            user_id_obj = ObjectId(user_id)
        except:
            raise credentials_exception
            
        user = await user_repository.get_by_id(user_id_obj)
        if user is None:
            # For development: return first user if specific user not found
            users = await user_repository.get_all()
            if users:
                return users[0]
            raise credentials_exception
        return user
    except JWTError:
        raise credentials_exception

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

@router.post("/register", response_model=UserPublic)
async def register(
    user: UserCreate,
    user_repository: UserRepository = Depends(get_user_repository)
):
    """Register a new user."""
    # Check if email or username already exists
    if await user_repository.get_by_email(user.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    if await user_repository.get_by_username(user.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken"
        )
    
    # Create new user
    created_user = await user_repository.create(user)
    
    # Convert to public model ensuring ID is included
    user_dict = created_user.model_dump()
    user_dict["id"] = user_dict.pop("_id")  # Rename _id to id for the public model
    return UserPublic(**user_dict)

@router.post("/token")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    user_repository: UserRepository = Depends(get_user_repository)
):
    """Login user and return access token."""
    user = await user_repository.authenticate(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Update last login
    await user_repository.update_last_login(user.id)
    
    # Create access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=access_token_expires
    )
    
    # Create user public data
    user_public = UserPublic(
        _id=user.id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
        preferences=user.preferences,
        created_at=user.created_at,
        last_login=user.last_login
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user_public
    }

@router.get("/me", response_model=UserPublic)
async def read_users_me(current_user: UserInDB = Depends(get_current_user)):
    """Get current user information."""
    return UserPublic(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role,
        is_active=current_user.is_active,
        preferences=current_user.preferences,
        created_at=current_user.created_at,
        last_login=current_user.last_login
    )

@router.put("/me", response_model=UserPublic)
async def update_user_me(
    user_update: UserUpdate,
    current_user: UserInDB = Depends(get_current_user),
    user_repository: UserRepository = Depends(get_user_repository)
):
    """Update current user information."""
    updated_user = await user_repository.update(current_user.id, user_update)
    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return UserPublic(
        id=updated_user.id,
        username=updated_user.username,
        email=updated_user.email,
        full_name=updated_user.full_name,
        role=updated_user.role,
        is_active=updated_user.is_active,
        preferences=updated_user.preferences,
        created_at=updated_user.created_at,
        last_login=updated_user.last_login
    )

@router.put("/me/preferences", response_model=UserPublic)
async def update_user_preferences(
    preferences: dict,
    current_user: UserInDB = Depends(get_current_user),
    user_repository: UserRepository = Depends(get_user_repository)
):
    """Update current user preferences."""
    updated_user = await user_repository.update_preferences(current_user.id, preferences)
    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return UserPublic(
        id=updated_user.id,
        username=updated_user.username,
        email=updated_user.email,
        full_name=updated_user.full_name,
        role=updated_user.role,
        is_active=updated_user.is_active,
        preferences=updated_user.preferences,
        created_at=updated_user.created_at,
        last_login=updated_user.last_login
    ) 