from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.student import CreateNewStudent, StudentResponse, UpdateStudent, StudentImportSchema
from app.core.database import get_db
from app.core.logger import logger
from app.services.auth import AuthService
from app.services.student import StudentService
from app.utils.roles import require_roles, Role

router = APIRouter(prefix="/student", tags=["Student"])


@router.get("/", response_model=List[StudentResponse], status_code=status.HTTP_200_OK)
async def get_students(
        db: AsyncSession = Depends(get_db),
        current_user: dict = Depends(require_roles([Role.ADMIN, Role.CURATOR]))
):
    """
    Получение списка всех студентов.

    Args:
        db: Асинхронная сессия SQLAlchemy
        current_user: Информация о текущем пользователе

    Returns:
        List[StudentResponse]: Список студентов с их данными

    Raises:
        HTTPException: 500 - Внутренняя ошибка сервера
    """
    try:
        students = await StudentService.get_all_students(db=db, current_user=current_user)
        logger.info(f"[ПОЛУЧЕНИЕ СТУДЕНТОВ] Получено {len(students)} студентов")

        return [
            StudentResponse(
                firstName=student.first_name,
                lastName=student.last_name,
                patronymic=student.patronymic,
                group_id=student.group_id,
                verif=student.verif,
                id=student.id,
                telephone=student.telephone,
                dateOfBirth=student.date_of_birth,
                mail=student.mail,
                snils=student.snils,
            ) for student in students
        ]

    except Exception as e:
        logger.error(f"[ПОЛУЧЕНИЕ СТУДЕНТОВ] Ошибка при получении списка студентов: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Произошла ошибка при получении списка студентов"
        ) from e


@router.post("/create", response_model=StudentResponse, status_code=status.HTTP_201_CREATED)
async def create_student(
        student_data: CreateNewStudent,
        db: AsyncSession = Depends(get_db),
        current_user: dict = Depends(require_roles([Role.ADMIN, Role.CURATOR]))
):
    """
    Создание нового студента.

    Args:
        student_data: Данные для создания студента
        db: Асинхронная сессия SQLAlchemy
        current_user: Информация о текущем пользователе

    Returns:
        StudentResponse: Созданный студент

    Raises:
        HTTPException: 400 - Ошибка валидации данных
        HTTPException: 500 - Внутренняя ошибка сервера
    """
    try:
        student = await AuthService.register_student(
            login=student_data.login,
            first_name=student_data.firstName,
            last_name=student_data.lastName,
            patronymic=student_data.patronymic,
            group_id=student_data.group_id,
            db=db
        )

        logger.info(f"[СОЗДАНИЕ СТУДЕНТА] Создан студент ID {student.id}, логин: {student.login}")

        return StudentResponse(
            firstName=student.first_name,
            lastName=student.last_name,
            patronymic=student.patronymic,
            group_id=student.group_id,
            id=student.id,
            telephone=student.telephone,
            dateOfBirth=student.date_of_birth,
            mail=student.mail,
            snils=student.snils,
        )

    except ValueError as e:
        logger.warning(f"[СОЗДАНИЕ СТУДЕНТА] Ошибка валидации: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        ) from e
    except Exception as e:
        logger.error(f"[СОЗДАНИЕ СТУДЕНТА] Ошибка при создании студента: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Произошла ошибка при создании студента"
        ) from e


@router.patch("/update/{student_id}", response_model=StudentResponse, status_code=status.HTTP_200_OK)
async def update_student(
        student_id: int,
        student_data: UpdateStudent,
        db: AsyncSession = Depends(get_db),
        current_user: dict = Depends(require_roles([Role.ADMIN, Role.CURATOR, Role.STUDENT]))
):
    """
    Обновление информации о студенте по ID.

    Args:
        student_id: Идентификатор студента
        student_data: Новые данные студента
        db: Асинхронная сессия SQLAlchemy
        current_user: Информация о текущем пользователе

    Returns:
        StudentResponse: Обновленный студент

    Raises:
        HTTPException: 404 - Студент не найден
        HTTPException: 500 - Внутренняя ошибка сервера
    """
    try:
        updated_student = await StudentService.update_student(student_id, student_data, db)

        if not updated_student:
            logger.warning(f"[ОБНОВЛЕНИЕ СТУДЕНТА] Студент не найден: ID {student_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Студент не найден"
            )

        logger.info(f"[ОБНОВЛЕНИЕ СТУДЕНТА] Студент обновлен: ID {student_id}")

        return StudentResponse(
            firstName=updated_student.first_name,
            lastName=updated_student.last_name,
            patronymic=updated_student.patronymic,
            group_id=updated_student.group_id,
            verif=updated_student.verif,
            telephone=updated_student.telephone,
            dateOfBirth=updated_student.date_of_birth,
            mail=updated_student.mail,
            snils=updated_student.snils,
            id=updated_student.id,
        )

    except Exception as e:
        logger.error(f"[ОБНОВЛЕНИЕ СТУДЕНТА] Ошибка при обновлении студента ID {student_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Произошла ошибка при обновлении студента"
        ) from e


@router.get("/{group_id}/students", response_model=List[StudentResponse])
async def get_students_by_id(
        group_id: int,
        exam_id: int,
        db: AsyncSession = Depends(get_db),
        current_user: dict = Depends(require_roles([Role.ADMIN, Role.CURATOR]))
):
    """
    Получение списка студентов по идентификатору группы.

    Args:
        group_id: Идентификатор группы
        db: Асинхронная сессия SQLAlchemy
        current_user: Информация о текущем пользователе

    Returns:
        List[StudentResponse]: Список студентов группы

    Raises:
        HTTPException: 404 - Группа не найдена
        HTTPException: 500 - Внутренняя ошибка сервера
    """
    try:
        student_grade_pairs = await StudentService.get_students_by_group_id(group_id, db, exam_id)

        if not student_grade_pairs:
            logger.warning(f"[ПОЛУЧЕНИЕ СТУДЕНТОВ] Группа не найдена: ID {group_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Группа не найдена"
            )

        logger.info(f"[ПОЛУЧЕНИЕ СТУДЕНТОВ] Получено {len(student_grade_pairs)} студентов для группы ID {group_id}")

        return [
            StudentResponse(
                firstName=student.first_name,
                lastName=student.last_name,
                patronymic=student.patronymic,
                id=student.id,
                grade=grade
            ) for student, grade in student_grade_pairs
        ]

    except Exception as e:
        logger.error(f"[ПОЛУЧЕНИЕ СТУДЕНТОВ] Ошибка при получении студентов группы ID {group_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Произошла ошибка при получении студентов"
        ) from e


@router.get("/by-login/{login}", response_model=StudentResponse, status_code=status.HTTP_200_OK)
async def get_student_by_login(
        login: str,
        db: AsyncSession = Depends(get_db),
        current_user: dict = Depends(require_roles([Role.ADMIN, Role.CURATOR, Role.STUDENT]))
):
    """
    Получение информации о студенте по его логину.

    Args:
        login: Логин студента
        db: Асинхронная сессия SQLAlchemy
        current_user: Информация о текущем пользователе

    Returns:
        StudentResponse: Данные студента

    Raises:
        HTTPException: 404 - Студент не найден
        HTTPException: 500 - Внутренняя ошибка сервера
    """
    try:
        student = await StudentService.get_student_by_login(login, db)

        if not student:
            logger.warning(f"[ПОЛУЧЕНИЕ СТУДЕНТА] Студент не найден: логин {login}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Студент не найден"
            )

        group_name = student.group.name if student.group else None
        curator = student.group.curator if student.group and student.group.curator else None
        curator_fullname = None

        if curator:
            curator_fullname = f"{curator.last_name} {curator.first_name} {curator.patronymic}"

        logger.info(f"[ПОЛУЧЕНИЕ СТУДЕНТА] Найден студент: логин {login}")

        return {
            "firstName": student.first_name,
            "lastName": student.last_name,
            "patronymic": student.patronymic,
            "group_id": student.group_id,
            "group_name": group_name,
            "curator_fullname": curator_fullname,
            "verif": student.verif,
            "id": student.id,
            "telephone": student.telephone,
            "dateOfBirth": student.date_of_birth,
            "mail": student.mail,
            "snils": student.snils,
            "tg_id": student.telegram.telegram_id if student.telegram else None
        }

    except Exception as e:
        logger.error(f"[ПОЛУЧЕНИЕ СТУДЕНТА] Ошибка при получении студента по логину {login}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Произошла ошибка при получении данных студента"
        ) from e


@router.delete("/delete/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_student(
        student_id: int,
        db: AsyncSession = Depends(get_db),
        current_user: dict = Depends(require_roles([Role.ADMIN, Role.CURATOR]))
):
    """
    Удаление студента по ID.

    Args:
        student_id: Идентификатор студента
        db: Асинхронная сессия SQLAlchemy
        current_user: Информация о текущем пользователе

    Returns:
        Response: 204 No Content при успешном удалении

    Raises:
        HTTPException: 404 - Студент не найден
        HTTPException: 500 - Внутренняя ошибка сервера
    """
    try:
        deleted = await StudentService.delete_student(student_id, db)

        if not deleted:
            logger.warning(f"[УДАЛЕНИЕ СТУДЕНТА] Студент не найден: ID {student_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Студент не найден"
            )

        logger.info(f"[УДАЛЕНИЕ СТУДЕНТА] Студент удален: ID {student_id}")
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    except Exception as e:
        logger.error(f"[УДАЛЕНИЕ СТУДЕНТА] Ошибка при удалении студента ID {student_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Произошла ошибка при удалении студента"
        ) from e


@router.post("/import", status_code=status.HTTP_201_CREATED)
async def import_students(
        students_data: List[StudentImportSchema],
        db: AsyncSession = Depends(get_db),
        current_user: dict = Depends(require_roles([Role.ADMIN, Role.CURATOR]))
):
    """
    Массовый импорт студентов из таблицы.

    Args:
        students_data: Список данных для импорта студентов
        db: Асинхронная сессия SQLAlchemy
        current_user: Информация о текущем пользователе

    Returns:
        dict: Результат импорта с количеством импортированных студентов и ошибками

    Raises:
        HTTPException: 400 - Ошибка валидации данных
        HTTPException: 500 - Внутренняя ошибка сервера
    """
    try:
        imported_count, errors = await StudentService.import_students_from_table(students_data, db)

        logger.info(f"[ИМПОРТ СТУДЕНТОВ] Импортировано {imported_count} студентов из {len(students_data)} записей")

        return {
            "message": f"Импортировано студентов: {imported_count}",
            "errors": errors,
            "total_attempts": len(students_data)
        }

    except ValueError as e:
        logger.warning(f"[ИМПОРТ СТУДЕНТОВ] Ошибка валидации: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        ) from e
    except Exception as e:
        logger.error(f"[ИМПОРТ СТУДЕНТОВ] Ошибка при импорте студентов: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Произошла ошибка при импорте студентов"
        ) from e