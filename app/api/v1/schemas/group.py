from typing import Optional

from pydantic import BaseModel, constr


class GroupResponse(BaseModel):
    group_id: int
    name: str
    curator_id: int
    students_count: Optional[int] = 0

class CreateGroup(BaseModel):
    name: str
    curator_id: int


class GroupImportSchema(BaseModel):
    name: constr(strip_whitespace=True)
    curator_full_name: constr(strip_whitespace=True)
