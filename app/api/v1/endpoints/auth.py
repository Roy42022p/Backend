from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Form, status
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.logger import logger
from app.services.auth import AuthService, Role
from app.api.v1.schemas.auth import TokenResponse, RegisterResponse

router = APIRouter(prefix="/auth", tags=["Auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


@router.post("/login", response_model=TokenResponse)
async def login(
        form_data: OAuth2PasswordRequestForm = Depends(),
        secret_key: Optional[str] = Form(None),
        db: AsyncSession = Depends(get_db)
):
    """
    Аутентификация пользователя (администратор или куратор) и выдача JWT-токена.

    Args:
        form_data: Данные формы OAuth2 (логин и пароль)
        secret_key: Секретный ключ для дополнительной аутентификации
        db: Асинхронная сессия SQLAlchemy

    Returns:
        TokenResponse: Объект с токеном, типом токена, ролью и именем пользователя

    Raises:
        HTTPException: 401 - Неверные учетные данные или секретный ключ
                      401 - Неизвестная роль пользователя
    """
    async with db.begin():
        auth_result = await AuthService.authenticate_user(
            form_data.username, form_data.password, db
        )

    if not auth_result:
        logger.warning("[АВТОРИЗАЦИЯ] Неудачная попытка входа: неверные учетные данные")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль"
        )

    user, role = auth_result["user"], auth_result["role"]

    if not AuthService.verify_secret_key(secret_key, role):
        logger.warning(f"[АВТОРИЗАЦИЯ] Неверный секретный ключ для пользователя {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный секретный ключ"
        )

    access_token = AuthService.create_token(user.login, role, user.id)

    logger.info(f"[АВТОРИЗАЦИЯ] Успешный вход: {form_data.username}, роль: {role.value}")
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        role=role.value,
        username=form_data.username
    )


@router.post("/register", response_model=RegisterResponse)
async def register(
        username: str = Form(...),
        password: str = Form(...),
        secret_key: str = Form(...),
        db: AsyncSession = Depends(get_db)
):
    """
    Регистрация нового администратора.

    Args:
        username: Имя пользователя
        password: Пароль
        secret_key: Секретный ключ для проверки прав на регистрацию
        db: Асинхронная сессия SQLAlchemy

    Returns:
        RegisterResponse: Объект с данными зарегистрированного администратора

    Raises:
        HTTPException: 401 - Неверный секретный ключ
                      403 - Регистрация не для администратора
                      400 - Ошибка валидации данных
    """
    role = AuthService.get_role_by_key(secret_key)

    if not role:
        logger.warning("[РЕГИСТРАЦИЯ] Неверный секретный ключ при регистрации")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный секретный ключ"
        )

    if role != Role.ADMIN:
        logger.warning(f"[РЕГИСТРАЦИЯ] Попытка регистрации недопустимой роли: {role.value}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Регистрация доступна только для администраторов"
        )

    try:
        async with db.begin():
            admin = await AuthService.register_admin(username, password, db)
            access_token = AuthService.create_token(admin.login, role, admin.id)
            logger.info(f"[РЕГИСТРАЦИЯ] Администратор зарегистрирован: {admin.login}")
            return RegisterResponse(
                username=admin.login,
                role=role.value,
                access_token=access_token
            )

    except ValueError as e:
        logger.error(f"[РЕГИСТРАЦИЯ] Ошибка регистрации администратора {username}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )