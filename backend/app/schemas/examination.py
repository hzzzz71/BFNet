"""
检查记录 schemas
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class PolypBase(BaseModel):
    """息肉基础信息"""
    location: Optional[str] = Field(None, description="息肉位置")
    size_mm: Optional[float] = Field(None, description="息肉大小（毫米）")
    shape_type: Optional[str] = Field(None, description="息肉形态类型")
    boundary_score: Optional[float] = Field(None, description="边界清晰度分数")
    confidence: Optional[float] = Field(None, description="置信度")
    bbox_coords: Optional[Dict[str, Any]] = Field(None, description="边界框坐标")


class PolypCreate(PolypBase):
    """创建息肉"""
    examination_id: str


class PolypUpdate(PolypBase):
    """更新息肉"""
    pass


class PolypInDB(PolypBase):
    """数据库中的息肉记录"""
    id: str
    examination_id: str
    
    class Config:
        from_attributes = True


class ExaminationBase(BaseModel):
    """检查记录基础信息"""
    patient_id: str
    exam_date: Optional[datetime] = Field(None, description="检查日期")
    image_path: Optional[str] = Field(None, description="原始图像路径")
    result_path: Optional[str] = Field(None, description="分割结果路径")
    report_path: Optional[str] = Field(None, description="报告路径")
    exam_type: Optional[str] = Field("colonoscopy", description="检查类型")
    polyp_count: Optional[int] = Field(0, description="息肉数量")
    risk_level: Optional[str] = Field("unknown", description="风险等级")
    pathology_type: Optional[str] = Field(None, description="病理类型")
    recommended_followup: Optional[int] = Field(None, description="建议复查天数")
    doctor_notes: Optional[str] = Field(None, description="医生备注")
    llm_analysis: Optional[Dict[str, Any]] = Field(None, description="LLM分析结果")
    llm_model_key: Optional[str] = Field(None, description="本次分析所选模型键")
    llm_model_id: Optional[str] = Field(None, description="本次分析实际模型ID")
    doctor_confirmed_report: Optional[Dict[str, Any]] = Field(None, description="医生确认版报告")
    doctor_reviewed: Optional[bool] = Field(False, description="医生是否已确认")
    doctor_reviewed_at: Optional[datetime] = Field(None, description="医生确认时间")


class ExaminationCreate(ExaminationBase):
    """创建检查记录"""
    pass


class ExaminationUpdate(BaseModel):
    """更新检查记录"""
    exam_date: Optional[datetime] = None
    image_quality: Optional[str] = None
    risk_level: Optional[str] = None
    llm_analysis: Optional[Dict[str, Any]] = None


class ExaminationInDB(ExaminationBase):
    """数据库中的检查记录"""
    id: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class ExaminationDetail(ExaminationInDB):
    """检查记录详情（含息肉列表）"""
    polyps: List[PolypInDB] = Field(default_factory=list)


class ExaminationList(BaseModel):
    """检查记录列表"""
    id: str
    patient_id: str
    exam_date: Optional[datetime] = None
    exam_type: Optional[str] = None
    polyp_count: int = 0
    risk_level: Optional[str] = None
    pathology_type: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class ExaminationResponse(ExaminationInDB):
    polyps: List[PolypInDB] = Field(default_factory=list)


class DoctorReviewUpdate(BaseModel):
    risk_level: str
    pathology_type: str
    treatment_recommendation: str
    followup_plan: str
    clinical_report: str
    historical_comparison: Optional[str] = None
    progression_assessment: Optional[str] = None


class AnalysisRequest(BaseModel):
    llm_model_key: Optional[str] = Field(None, description="本次分析所选模型键")


class LLMModelOption(BaseModel):
    key: str
    label: str
    provider: str
    available: bool
    default: bool
