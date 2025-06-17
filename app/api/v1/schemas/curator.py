from typing import List

from pydantic import BaseModel, constr
from typing_extensions import Optional


class CuratorResponse(BaseModel):
    firstName: str
    lastName: str
    patronymic: str
    curator_id: Optional[int] = None
    login: Optional[str] = None
    groups: Optional[List[str]] = None

class CreateNewCurator(BaseModel):
    firstName: str
    lastName: str
    patronymic: str
    login: str
    password: str

class UpdateCurator(BaseModel):
    firstName: Optional[str]
    lastName: Optional[str]
    patronymic: Optional[str]
    login: Optional[str]


class CuratorImportSchema(BaseModel):
    full_name: constr(strip_whitespace=True)
    groups: List[str] = []
    login: str
    password: str