import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import date

# Добавляем корень проекта в PYTHOPATH
sys.path.insert(0, str(Path(__file__).parent.parent))

from main import app
import database
from database import Base

# Настройка тестовой базы данных
TEST_DB_URL = "sqlite:///./test.db"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Фикстура для БД (выполняется для каждой функции)
@pytest.fixture(scope="function")
def db():
    # Создаем все таблицы
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        # Удаляем все таблицы после теста
        Base.metadata.drop_all(bind=engine)


# Фикстура для клиента (пересоздается для каждого теста)
@pytest.fixture(scope="function")
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            db.rollback()

    app.dependency_overrides[database.get_db] = override_get_db
    return TestClient(app)


# Фикстуры для тестовых данных
@pytest.fixture
def test_teacher():
    return {
        "email": "teacher@example.com",
        "full_name": "Test Teacher",
        "password": "testpassword"
    }


@pytest.fixture
def test_student():
    return {
        "full_name": "Test Student",
        "class_group": "10A"
    }


@pytest.fixture
def test_subject():
    return {"name": "Mathematics"}


@pytest.fixture
def test_grade():
    return {
        "student_id": 1,
        "subject_id": 1,
        "grade": 5,
        "date": str(date.today())
    }


# Тесты
def test_teacher_registration(client, test_teacher):
    response = client.post("/teachers/register/", json=test_teacher)
    assert response.status_code == 200
    assert response.json()["email"] == test_teacher["email"]


def test_teacher_login(client, test_teacher):
    client.post("/teachers/register/", json=test_teacher)
    response = client.post("/teachers/login/", data={
        "username": test_teacher["email"],
        "password": test_teacher["password"]
    })
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_create_student(client, test_student):
    response = client.post("/students/", json=test_student)
    assert response.status_code == 201
    assert response.json()["full_name"] == test_student["full_name"]


def test_get_student(client, test_student):
    # Создаем студента
    create_resp = client.post("/students/", json=test_student)
    student_id = create_resp.json()["id"]

    # Получаем студента
    response = client.get(f"/students/{student_id}")
    assert response.status_code == 200
    assert response.json()["full_name"] == test_student["full_name"]


def test_create_subject(client, test_subject):
    response = client.post("/subjects/", json=test_subject)
    assert response.status_code == 200
    assert response.json()["name"] == test_subject["name"]


def test_create_grade(client, test_student, test_subject, test_grade):
    # Создаем необходимые данные
    client.post("/students/", json=test_student)
    client.post("/subjects/", json=test_subject)

    # Создаем оценку
    response = client.post("/grades/", json=test_grade)
    assert response.status_code == 201
    assert response.json()["grade"] == test_grade["grade"]


def test_student_stats(client, test_student, test_subject, test_grade):
    # Подготавливаем данные
    client.post("/students/", json=test_student)
    client.post("/subjects/", json=test_subject)
    client.post("/grades/", json=test_grade)

    # Получаем статистику
    response = client.get("/students/1/stats")
    assert response.status_code == 200
    assert response.json()["average_grade"] == 5.0
    assert "Mathematics" in response.json()["subjects"]


def test_protected_endpoint(client, test_teacher):
    # Регистрация и логин
    client.post("/teachers/register/", json=test_teacher)
    login_resp = client.post("/teachers/login/", data={
        "username": test_teacher["email"],
        "password": test_teacher["password"]
    })
    token = login_resp.json()["access_token"]

    # Защищенный эндпоинт
    response = client.get(
        "/teachers/me/",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.json()["email"] == test_teacher["email"]
