"""
息肉详细信息数据模型
"""

from sqlalchemy import Column, String, Integer, ForeignKey, DECIMAL, JSON
from sqlalchemy.orm import relationship
from app.core.database import Base
import uuid


class Polyp(Base):
    __tablename__ = "polyps"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    examination_id = Column(String(36), ForeignKey("examinations.id"), nullable=False, index=True)
    
    polyp_number = Column(Integer, comment="息肉编号")
    location = Column(String(200), comment="位置描述")
    size_mm = Column(DECIMAL(5, 2), comment="直径(mm)")
    boundary_score = Column(DECIMAL(3, 2), comment="边界清晰度(0-1)")
    
    shape_type = Column(String(50), comment="形态类型: pedunculated/sessile/flat")
    surface_pattern = Column(String(100), comment="表面形态")
    pathology_pred = Column(String(100), comment="病理预测")
    confidence_score = Column(DECIMAL(3, 2), comment="置信度")
    
    bbox_coords = Column(JSON, comment="边界框坐标")
    
    # 关系
    examination = relationship("Examination", back_populates="polyps")
    
    def __repr__(self):
        return f"<Polyp(id={self.id}, exam_id={self.examination_id}, number={self.polyp_number})>"
