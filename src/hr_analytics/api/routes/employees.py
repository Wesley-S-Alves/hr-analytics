"""Rotas CRUD de colaboradores."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from hr_analytics.api.dependencies import get_db
from hr_analytics.inference.schemas import (
    EmployeeCreate,
    EmployeeListResponse,
    EmployeeResponse,
    EmployeeUpdate,
)
from hr_analytics.models.db_models import Employee

router = APIRouter(prefix="/employees", tags=["Colaboradores"])

# Whitelist de campos atualizáveis via PUT — defense in depth acima do schema Pydantic.
# Bloqueia tentativas de alterar id, created_at, is_active, risk_score etc.
ALLOWED_UPDATE_FIELDS = {
    "age",
    "department",
    "job_role",
    "job_level",
    "monthly_income",
    "over_time",
    "environment_satisfaction",
    "job_satisfaction",
    "work_life_balance",
}


@router.get("", response_model=EmployeeListResponse)
def list_employees(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    risk_level: str | None = Query(None, description="Filtrar por nível de risco"),
    department: str | None = Query(None, description="Filtrar por departamento"),
    db: Session = Depends(get_db),
):
    """Lista colaboradores com paginação e filtros."""
    query = db.query(Employee).filter(Employee.is_active.is_(True))

    if risk_level:
        query = query.filter(Employee.risk_level == risk_level)
    if department:
        query = query.filter(Employee.department == department)

    total = query.count()
    employees = query.order_by(Employee.id).offset((page - 1) * page_size).limit(page_size).all()

    return EmployeeListResponse(
        employees=[EmployeeResponse.model_validate(e) for e in employees],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{employee_id}", response_model=EmployeeResponse)
def get_employee(employee_id: int, db: Session = Depends(get_db)):
    """Retorna detalhes de um colaborador."""
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Colaborador não encontrado")
    return EmployeeResponse.model_validate(employee)


@router.post("", response_model=EmployeeResponse, status_code=201)
def create_employee(data: EmployeeCreate, db: Session = Depends(get_db)):
    """Cadastra um novo colaborador."""
    employee = Employee(**data.model_dump())
    db.add(employee)
    db.commit()
    db.refresh(employee)
    return EmployeeResponse.model_validate(employee)


@router.put("/{employee_id}", response_model=EmployeeResponse)
def update_employee(
    employee_id: int,
    data: EmployeeUpdate,
    db: Session = Depends(get_db),
):
    """Atualiza dados de um colaborador."""
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Colaborador não encontrado")

    update_data = data.model_dump(exclude_unset=True)
    # Whitelist explícita — nunca permite campos sensíveis (id, is_active, risk_score, etc.)
    safe_fields = {k: v for k, v in update_data.items() if k in ALLOWED_UPDATE_FIELDS}
    rejected = set(update_data) - ALLOWED_UPDATE_FIELDS
    if rejected:
        raise HTTPException(
            status_code=400,
            detail=f"Campos não permitidos na atualização: {sorted(rejected)}",
        )
    for field, value in safe_fields.items():
        setattr(employee, field, value)

    db.commit()
    db.refresh(employee)
    return EmployeeResponse.model_validate(employee)


@router.delete("/{employee_id}", status_code=204)
def delete_employee(employee_id: int, db: Session = Depends(get_db)):
    """Soft delete de um colaborador (marca como inativo)."""
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Colaborador não encontrado")

    employee.is_active = False
    db.commit()
