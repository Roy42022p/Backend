from pydantic import BaseModel, constr
from typing import List, Optional


class MarkUpdateItem(BaseModel):
    student_id: int
    exam_id: int
    mark: constr(strip_whitespace=True, max_length=5)

class MarkUpdateBatch(BaseModel):
    marks: List[MarkUpdateItem]

class MarkImportSchema(BaseModel):
    id: int
    last_fist_name: constr(strip_whitespace=True)
    mark: Optional[constr(strip_whitespace=True, max_length=5)] = None