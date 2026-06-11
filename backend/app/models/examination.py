"""
检查记录数据模型
"""

from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey, DECIMAL, JSON, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base
import uuid


class Examination(Base):
    __tablename__ = "examinations"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = Column(String(36), ForeignKey("patients.id"), nullable=False, index=True)
    exam_date = Column(DateTime(timezone=True), nullable=False, comment="检查日期")
    exam_type = Column(String(50), default="colonoscopy", comment="检查类型")
    
    # 文件路径
    image_path = Column(String(500), comment="原始图像路径")
    result_path = Column(String(500), comment="分割结果路径")
    report_path = Column(String(500), comment="生成报告路径")
    
    # 分割结果
    polyp_count = Column(Integer, default=0, comment="息肉数量")
    risk_level = Column(String(20), comment="风险等级: low/medium/high")
    pathology_type = Column(String(100), comment="病理类型")
    recommended_followup = Column(Integer, comment="建议复查天数")
    
    # LLM分析结果 (JSON存储)
    llm_analysis = Column(JSON, comment="LLM分析结果")
    llm_model_key = Column(String(50), comment="本次分析所选模型键")
    llm_model_id = Column(String(100), comment="本次分析实际模型ID")
    
    doctor_notes = Column(Text, comment="医生备注")
    doctor_confirmed_report = Column(JSON, comment="医生确认版报告")
    doctor_reviewed = Column(Boolean, default=False, comment="医生是否已审核确认")
    doctor_reviewed_at = Column(DateTime(timezone=True), comment="医生审核时间")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 关系
    patient = relationship("Patient", back_populates="examinations")
    polyps = relationship("Polyp", back_populates="examination", cascade="all, delete-orphan")
    followup_plans = relationship("FollowupPlan", back_populates="examination")
    
    def __repr__(self):
        return f"<Examination(id={self.id}, patient_id={self.patient_id}, date={self.exam_date})>"
