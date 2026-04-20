"""Rotas CRUD de usuários do sistema."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from hr_analytics.api.dependencies import get_db
from hr_analytics.inference.schemas import UserCreate, UserResponse
from hr_analytics.models.db_models import User

router = APIRouter(prefix="/users", tags=["Usuários"])


@router.get("", response_model=list[UserResponse])
def list_users(db: Session = Depends(get_db)):
    """Lista todos os usuários ativos."""
    users = db.query(User).filter(User.is_active.is_(True)).all()
    return [UserResponse.model_validate(u) for u in users]


@router.post("", response_model=UserResponse, status_code=201)
def create_user(data: UserCreate, db: Session = Depends(get_db)):
    """Cadastra um novo usuário."""
    existing = db.query(User).filter(User.email == data.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email já cadastrado")

    user = User(**data.model_dump())
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserResponse.model_validate(user)
