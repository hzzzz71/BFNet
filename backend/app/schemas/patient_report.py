"""
患者报告 schemas
"""

from datetime import datetime
from pydantic import BaseModel


class PatientReportInDB(BaseModel):
    id: str
    patient_id: str
    file_name: str
    file_path: str
    content_type: str | None = None
    file_size: int | None = None
    uploaded_at: datetime
    download_url: str

    class Config:
        from_attributes = True
