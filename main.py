from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import date, timedelta
from typing import List, Optional
import models
from database import get_db, engine, Base
import auth
from auth import get_current_teacher
import database

app = FastAPI()

Base.metadata.create_all(bind=engine)


# ========== Аутентификация ==========
@app.post("/register/", response_model=models.Teacher, status_code=status.HTTP_201_CREATED)
def register_teacher(
        teacher_data: models.TeacherCreate,
        db: Session = Depends(get_db)
):
    # Проверяем валидность email
    try:
        validated_email = models.TeacherBase(email=teacher_data.email, full_name=teacher_data.full_name).email
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )

    # Проверяем не зарегистрирован ли уже преподаватель
    db_teacher = auth.get_teacher_by_email(db, validated_email)
    if db_teacher:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Хешируем пароль и создаем преподавателя
    hashed_password = auth.get_password_hash(teacher_data.password)
    db_teacher = database.Teacher(
        email=validated_email,
        full_name=teacher_data.full_name,
        hashed_password=hashed_password
    )
    db.add(db_teacher)
    db.commit()
    db.refresh(db_teacher)
    return db_teacher


@app.post("/token", response_model=models.Token)
def login_for_access_token(
        form_data: OAuth2PasswordRequestForm = Depends(),
        db: Session = Depends(get_db)
):
    teacher = auth.authenticate_teacher(db, form_data.username, form_data.password)
    if not teacher:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Создаем токен доступа
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": teacher.email},
        expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/teachers/me/", response_model=models.Teacher)
def read_teachers_me(current_teacher: models.Teacher = Depends(get_current_teacher)):
    return current_teacher


# ========== Students Endpoints ==========
@app.post("/students/", response_model=models.Student)
def create_student(student: models.StudentCreate, db: Session = Depends(get_db)):
    db_student = database.Student(**student.dict())
    db.add(db_student)
    db.commit()
    db.refresh(db_student)
    return db_student


@app.get("/students/", response_model=List[models.Student])
def read_students(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(database.Student).offset(skip).limit(limit).all()


@app.get("/students/{student_id}", response_model=models.Student)
def read_student(student_id: int, db: Session = Depends(get_db)):
    db_student = db.query(database.Student).filter(database.Student.id == student_id).first()
    if not db_student:
        raise HTTPException(status_code=404, detail="Student not found")
    return db_student


@app.put("/students/{student_id}", response_model=models.Student)
def update_student(student_id: int, student: models.StudentCreate, db: Session = Depends(get_db)):
    db_student = db.query(database.Student).filter(database.Student.id == student_id).first()
    if not db_student:
        raise HTTPException(status_code=404, detail="Student not found")

    for key, value in student.dict().items():
        setattr(db_student, key, value)

    db.commit()
    db.refresh(db_student)
    return db_student


@app.delete("/students/{student_id}")
def delete_student(student_id: int, db: Session = Depends(get_db)):
    # Сначала удаляем все оценки студента
    db.query(database.Grade).filter(database.Grade.student_id == student_id).delete()

    # Затем удаляем самого студента
    db_student = db.query(database.Student).filter(database.Student.id == student_id).first()
    if not db_student:
        raise HTTPException(status_code=404, detail="Student not found")

    db.delete(db_student)
    db.commit()
    return {"message": "Student deleted successfully"}


# ========== Subjects Endpoints ==========
@app.post("/subjects/", response_model=models.Subject)
def create_subject(subject: models.SubjectCreate, db: Session = Depends(get_db)):
    db_subject = database.Subject(**subject.dict())
    db.add(db_subject)
    db.commit()
    db.refresh(db_subject)
    return db_subject


@app.get("/subjects/", response_model=List[models.Subject])
def read_subjects(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(database.Subject).offset(skip).limit(limit).all()


@app.get("/subjects/{subject_id}", response_model=models.Subject)
def read_subject(subject_id: int, db: Session = Depends(get_db)):
    db_subject = db.query(database.Subject).filter(database.Subject.id == subject_id).first()
    if not db_subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    return db_subject


@app.put("/subjects/{subject_id}", response_model=models.Subject)
def update_subject(subject_id: int, subject: models.SubjectCreate, db: Session = Depends(get_db)):
    db_subject = db.query(database.Subject).filter(database.Subject.id == subject_id).first()
    if not db_subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    for key, value in subject.dict().items():
        setattr(db_subject, key, value)

    db.commit()
    db.refresh(db_subject)
    return db_subject


@app.delete("/subjects/{subject_id}")
def delete_subject(subject_id: int, db: Session = Depends(get_db)):
    # Проверяем есть ли оценки по этому предмету
    has_grades = db.query(database.Grade).filter(database.Grade.subject_id == subject_id).first()
    if has_grades:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete subject with existing grades. Delete grades first."
        )

    db_subject = db.query(database.Subject).filter(database.Subject.id == subject_id).first()
    if not db_subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    db.delete(db_subject)
    db.commit()
    return {"message": "Subject deleted successfully"}


# ========== Grades Endpoints ==========
@app.post("/grades/", response_model=models.Grade)
def create_grade(grade: models.GradeCreate, db: Session = Depends(get_db)):
    # Проверяем что оценка от 1 до 5
    if grade.grade < 1 or grade.grade > 5:
        raise HTTPException(status_code=400, detail="Grade must be between 1 and 5")

    # Проверяем что студент существует
    student = db.query(database.Student).filter(database.Student.id == grade.student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # Проверяем что предмет существует
    subject = db.query(database.Subject).filter(database.Subject.id == grade.subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    db_grade = database.Grade(**grade.dict())
    db.add(db_grade)
    db.commit()
    db.refresh(db_grade)
    return db_grade


@app.get("/grades/", response_model=List[models.Grade])
def read_grades(
        student_id: Optional[int] = None,
        subject_id: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        skip: int = 0,
        limit: int = 100,
        db: Session = Depends(get_db)
):
    query = db.query(database.Grade)

    if student_id:
        query = query.filter(database.Grade.student_id == student_id)
    if subject_id:
        query = query.filter(database.Grade.subject_id == subject_id)
    if start_date:
        query = query.filter(database.Grade.date >= start_date)
    if end_date:
        query = query.filter(database.Grade.date <= end_date)

    return query.offset(skip).limit(limit).all()


@app.get("/grades/{grade_id}", response_model=models.Grade)
def read_grade(grade_id: int, db: Session = Depends(get_db)):
    db_grade = db.query(database.Grade).filter(database.Grade.id == grade_id).first()
    if not db_grade:
        raise HTTPException(status_code=404, detail="Grade not found")
    return db_grade


@app.put("/grades/{grade_id}", response_model=models.Grade)
def update_grade(grade_id: int, grade: models.GradeCreate, db: Session = Depends(get_db)):
    if grade.grade < 1 or grade.grade > 5:
        raise HTTPException(status_code=400, detail="Grade must be between 1 and 5")

    db_grade = db.query(database.Grade).filter(database.Grade.id == grade_id).first()
    if not db_grade:
        raise HTTPException(status_code=404, detail="Grade not found")

    # Проверяем что студент существует
    student = db.query(database.Student).filter(database.Student.id == grade.student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # Проверяем что предмет существует
    subject = db.query(database.Subject).filter(database.Subject.id == grade.subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    for key, value in grade.dict().items():
        setattr(db_grade, key, value)

    db.commit()
    db.refresh(db_grade)
    return db_grade


@app.delete("/grades/{grade_id}")
def delete_grade(grade_id: int, db: Session = Depends(get_db)):
    db_grade = db.query(database.Grade).filter(database.Grade.id == grade_id).first()
    if not db_grade:
        raise HTTPException(status_code=404, detail="Grade not found")

    db.delete(db_grade)
    db.commit()
    return {"message": "Grade deleted successfully"}


# ========== Statistics Endpoint ==========
@app.get("/students/{student_id}/stats")
def get_student_stats(student_id: int, db: Session = Depends(get_db)):
    # Проверяем что студент существует
    student = db.query(database.Student).filter(database.Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # Получаем все оценки студента
    grades = db.query(database.Grade).filter(database.Grade.student_id == student_id).all()

    if not grades:
        return {"message": "No grades found for this student"}

    # Вычисляем средний балл
    avg_grade = sum(grade.grade for grade in grades) / len(grades)

    # Группируем оценки по предметам
    from collections import defaultdict
    subjects_grades = defaultdict(list)
    for grade in grades:
        subject = db.query(database.Subject).filter(database.Subject.id == grade.subject_id).first()
        subjects_grades[subject.name].append(grade.grade)

    # Вычисляем средний балл по каждому предмету
    subjects_avg = {subject: sum(grades) / len(grades)
                    for subject, grades in subjects_grades.items()}

    return {
        "student_id": student_id,
        "full_name": student.full_name,
        "class_group": student.class_group,
        "average_grade": round(avg_grade, 2),
        "subjects": subjects_avg
    }
