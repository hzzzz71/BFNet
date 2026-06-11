"""
患者报告数据模型
"""

from sqlalchemy import Column, String, DateTime, Integer, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base
import uuid


class PatientReport(Base):
    __tablename__ = "patient_reports"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = Column(String(36), ForeignKey("patients.id"), nullable=False, index=True)
    file_name = Column(String(255), nullable=False, comment="原始文件名")
    file_path = Column(String(500), nullable=False, comment="存储路径")
    content_type = Column(String(100), nullable=True, comment="文件类型")
    file_size = Column(Integer, nullable=True, comment="文件大小(字节)")
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    patient = relationship("Patient", back_populates="reports")

    def __repr__(self):
        return f"<PatientReport(id={self.id}, patient_id={self.patient_id}, file_name='{self.file_name}')>"
