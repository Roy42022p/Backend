from typing import Optional, List

from pydantic import BaseModel, constr


class StudentResponse(BaseModel):
    firstName: str
    lastName: str
    patronymic: str
    group_id: Optional[int] = None
    verif: Optional[bool] = None
    telephone: Optional[str] = None
    dateOfBirth: Optional[str] = None
    mail: Optional[str] = None
    snils: Optional[str] = None
    id: Optional[int] = None
    grade: Optional[int] = None
    curator_fullname: Optional[str] = None
    group_name: Optional[str] = None
    tg_id: Optional[int] = None


class CreateNewStudent(BaseModel):
    login: str
    firstName: str
    lastName: str
    patronymic: str
    group_id: Optional[int] = None
    verif: bool = False

class UpdateStudent(BaseModel):
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    patronymic: Optional[str] = None
    group_id: Optional[int] = None
    telephone: Optional[str] = None
    dateOfBirth: Optional[str] = None
    mail: Optional[str] = None
    snils: Optional[str] = None

class StudentImportSchema(BaseModel):
    full_name: constr(strip_whitespace=True)
    group_name: constr(strip_whitespace=True)