from fastapi import APIRouter
from app.api.v1.endpoints import auth, curator, student, group, exam, mark

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(curator.router)
api_router.include_router(student.router)
api_router.include_router(group.router)
api_router.include_router(exam.router)
api_router.include_router(mark.router)