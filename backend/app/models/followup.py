"""
随访计划数据模型
"""

from sqlalchemy import Column, String, Integer, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base
import uuid


class FollowupPlan(Base):
    __tablename__ = "followup_plans"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id = Column(String(36), ForeignKey("patients.id"), nullable=False, index=True)
    examination_id = Column(String(36), ForeignKey("examinations.id"), nullable=False)
    
    next_exam_date = Column(DateTime(timezone=True), nullable=False, comment="下次检查日期")
    status = Column(String(20), default="pending", comment="状态: pending/completed/overdue")
    reminder_sent = Column(Boolean, default=False, comment="是否已发送提醒")
    notes = Column(Text, comment="备注")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 关系
    patient = relationship("Patient", back_populates="followup_plans")
    examination = relationship("Examination")
    
    def __repr__(self):
        return f"<FollowupPlan(id={self.id}, patient_id={self.patient_id}, next_date={self.next_exam_date})>"
