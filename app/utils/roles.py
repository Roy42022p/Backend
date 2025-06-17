from enum import Enum
from typing import List

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.logger import logger
from app.core.jwt import verify_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


class Role(str, Enum):
    ADMIN = "admin"
    CURATOR = "curator"
    STUDENT = "student"


async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    """
    Зависимость для получения текущего пользователя и его роли из JWT-токена.

    Проверяет валидность токена через AuthService и возвращает данные пользователя, включая логин и роль.

    Args:
        token (str): JWT-токен, полученный через OAuth2-схему.
        db (AsyncSession): Асинхронная сессия базы данных.

    Returns:
        dict: Данные пользователя, содержащие логин и роль.

    Raises:
        HTTPException: Код 401, если токен недействителен или истёк.
    """
    async with db.begin():
        user_data = verify_token(token)

    if not user_data:
        logger.warning("[АУТЕНТИФИКАЦИЯ] Неверный или истекший токен")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный или истекший токен",
            headers={"WWW-Authenticate": "Bearer"},
        )
    logger.info(f"[АУТЕНТИФИКАЦИЯ] Пользователь аутентифицирован: {user_data['sub']}, роль: {user_data['role']}")
    return user_data


def require_roles(allowed_roles: List[Role]):
    """
    Фабрика зависимостей для проверки, что текущий пользователь имеет одну из разрешённых ролей.

    Args:
        allowed_roles (List[Role]): Список разрешённых ролей.

    Returns:
        Callable: Зависимость, проверяющая роль пользователя.
    """
    async def role_checker(current_user: dict = Depends(get_current_user)):
        if current_user["role"] not in allowed_roles:
            logger.warning(
                f"[АВТОРИЗАЦИЯ] Запрет доступа для пользователя '{current_user['sub']}' | "
                f"Роль: {current_user['role']} | Требуется: {', '.join(allowed_roles)}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Недостаточно прав доступа"
            )

        logger.info(
            f"[АВТОРИЗАЦИЯ] Доступ разрешён для пользователя '{current_user['sub']}' | "
            f"Роль: {current_user['role']} | Разрешено: {', '.join(allowed_roles)}"
        )
        return current_user

    return role_checker