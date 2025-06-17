from typing import Optional, List

from pydantic import BaseModel

from enum import Enum

class ExamType(str, Enum):
    EXAM = "exam"
    CREDITS = "credits"


class CreateExam(BaseModel):
    type: ExamType
    type: str
    semester: int
    course: int
    discipline: str
    holding_date: str
    link: Optional[str] = None
    group_id: int
    curator_id: int


class ExamResponse(BaseModel):
    type: ExamType
    id: int
    type: str
    semester: int
    course: int
    discipline: str
    holding_date: str
    link: Optional[str] = None
    group_name: Optional[str] = None
    curator_full_name: Optional[str] = None
    group_id: Optional[int] = None

class UpdateExamLink(BaseModel):
    link: Optional[str] = None


class StudentMark(BaseModel):
    student_id: int
    student_full_name: str
    mark: Optional[int]

class ExamMarksResponse(BaseModel):
    exam_id: int
    discipline: str
    holding_date: str
    students: List[StudentMark]