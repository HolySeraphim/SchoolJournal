from pydantic import BaseModel, EmailStr, validator
from typing import Optional
from datetime import date


class TeacherBase(BaseModel):
    email: EmailStr
    full_name: str

    @validator('email')
    def email_must_contain_at(cls, v):
        if '@' not in v:
            raise ValueError('Invalid email format')
        return v.lower()


class TeacherCreate(TeacherBase):
    password: str


class Teacher(TeacherBase):
    id: int
    is_active: bool

    class Config:
        orm_mode = True


class StudentBase(BaseModel):
    full_name: str
    class_group: str


class StudentCreate(StudentBase):
    pass


class Student(StudentBase):
    id: int

    class Config:
        orm_mode = True


class SubjectBase(BaseModel):
    name: str


class SubjectCreate(SubjectBase):
    pass


class Subject(SubjectBase):
    id: int

    class Config:
        orm_mode = True


class GradeBase(BaseModel):
    student_id: int
    subject_id: int
    grade: int
    date: date


class GradeCreate(GradeBase):
    pass


class Grade(GradeBase):
    id: int

    class Config:
        orm_mode = True


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    email: Optional[str] = None
