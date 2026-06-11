"""
患者信息数据模型
"""

from sqlalchemy import Column, String, Integer, DateTime, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base
import uuid


class Patient(Base):
    __tablename__ = "patients"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False, index=True, comment="患者姓名")
    gender = Column(String(10), comment="性别")
    age = Column(Integer, comment="年龄")
    phone = Column(String(20), comment="联系电话")
    medical_history = Column(Text, comment="既往病史")
    allergies = Column(Text, comment="过敏史")
    family_history = Column(Text, comment="家族病史")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # 关系
    examinations = relationship("Examination", back_populates="patient")
    followup_plans = relationship("FollowupPlan", back_populates="patient")
    reports = relationship("PatientReport", back_populates="patient", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Patient(id={self.id}, name='{self.name}')>"
