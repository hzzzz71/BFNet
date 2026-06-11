"""
患者信息 schemas
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
from uuid import UUID


class PatientBase(BaseModel):
    """患者基础信息"""
    name: str = Field(..., description="患者姓名")
    age: Optional[int] = Field(None, description="年龄")
    gender: Optional[str] = Field(None, description="性别")
    phone: Optional[str] = Field(None, description="联系电话")
    medical_history: Optional[str] = Field(None, description="既往病史")
    allergies: Optional[str] = Field(None, description="过敏史")
    family_history: Optional[str] = Field(None, description="家族病史")


class PatientCreate(PatientBase):
    """创建患者"""
    pass


class PatientUpdate(BaseModel):
    """更新患者信息"""
    name: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    phone: Optional[str] = None
    medical_history: Optional[str] = None
    allergies: Optional[str] = None
    family_history: Optional[str] = None


class PatientInDB(PatientBase):
    """数据库中的患者记录"""
    id: UUID
    created_at: datetime
    updated_at: datetime
    total_examinations: Optional[int] = 0
    
    class Config:
        from_attributes = True


class PatientDetail(PatientInDB):
    """患者详情（含检查记录）"""
    examinations: List["ExaminationInDB"] = []


class PatientList(BaseModel):
    """患者列表"""
    total: int
    items: List[PatientInDB]
    
    class Config:
        from_attributes = True
