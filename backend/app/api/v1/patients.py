"""
患者管理API
"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List, Optional
from uuid import UUID
from pathlib import Path

from app.core.database import get_db
from app.core.config import settings
from app.models.patient import Patient
from app.models.patient_report import PatientReport
from app.schemas.patient import PatientCreate, PatientUpdate, PatientInDB
from app.schemas.patient_report import PatientReportInDB
from app.services.storage_service import storage_service

router = APIRouter()
PATIENT_COLUMNS = {column.name for column in Patient.__table__.columns}
ALLOWED_REPORT_EXTENSIONS = {".pdf", ".doc", ".docx"}


def _report_download_url(file_path: str) -> str:
    return f"/uploads/{Path(file_path).as_posix()}"


@router.post("/", response_model=PatientInDB, status_code=status.HTTP_201_CREATED)
async def create_patient(
    patient_data: PatientCreate,
    db: AsyncSession = Depends(get_db)
):
    """创建患者档案"""
    payload = patient_data.model_dump(exclude_unset=True, exclude_none=True)
    payload = {field: value for field, value in payload.items() if field in PATIENT_COLUMNS}
    patient = Patient(**payload)
    db.add(patient)
    await db.commit()
    await db.refresh(patient)
    return patient


@router.get("/", response_model=List[PatientInDB])
async def list_patients(
    skip: int = 0,
    limit: int = 100,
    name: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """获取患者列表"""
    query = select(Patient).order_by(desc(Patient.created_at))

    if name:
        query = query.where(Patient.name.contains(name))

    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    patients = result.scalars().all()

    return patients


@router.get("/{patient_id}", response_model=PatientInDB)
async def get_patient(
    patient_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """获取患者详细信息"""
    patient = await db.get(Patient, str(patient_id))
    if not patient:
        raise HTTPException(status_code=404, detail="患者不存在")
    return patient


@router.put("/{patient_id}", response_model=PatientInDB)
async def update_patient(
    patient_id: UUID,
    patient_data: PatientUpdate,
    db: AsyncSession = Depends(get_db)
):
    """更新患者信息"""
    patient = await db.get(Patient, str(patient_id))
    if not patient:
        raise HTTPException(status_code=404, detail="患者不存在")

    update_data = patient_data.model_dump(exclude_unset=True, exclude_none=True)
    update_data = {field: value for field, value in update_data.items() if field in PATIENT_COLUMNS}
    for field, value in update_data.items():
        setattr(patient, field, value)

    await db.commit()
    await db.refresh(patient)
    return patient


@router.delete("/{patient_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_patient(
    patient_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """删除患者档案"""
    patient = await db.get(Patient, str(patient_id))
    if not patient:
        raise HTTPException(status_code=404, detail="患者不存在")

    await db.delete(patient)
    await db.commit()
    return None


@router.get("/{patient_id}/reports", response_model=List[PatientReportInDB])
async def list_patient_reports(
    patient_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """获取患者上传报告列表"""
    patient = await db.get(Patient, str(patient_id))
    if not patient:
        raise HTTPException(status_code=404, detail="患者不存在")

    query = (
        select(PatientReport)
        .where(PatientReport.patient_id == str(patient_id))
        .order_by(desc(PatientReport.uploaded_at))
    )
    result = await db.execute(query)
    reports = result.scalars().all()
    return [
        PatientReportInDB(
            id=report.id,
            patient_id=report.patient_id,
            file_name=report.file_name,
            file_path=report.file_path,
            content_type=report.content_type,
            file_size=report.file_size,
            uploaded_at=report.uploaded_at,
            download_url=_report_download_url(report.file_path),
        )
        for report in reports
    ]


@router.post("/{patient_id}/reports", response_model=PatientReportInDB, status_code=status.HTTP_201_CREATED)
async def upload_patient_report(
    patient_id: UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """上传患者病例报告（PDF/DOC/DOCX）"""
    patient = await db.get(Patient, str(patient_id))
    if not patient:
        raise HTTPException(status_code=404, detail="患者不存在")

    file_name = file.filename or ""
    file_ext = Path(file_name).suffix.lower()
    if file_ext not in ALLOWED_REPORT_EXTENSIONS:
        raise HTTPException(status_code=422, detail="仅支持上传 PDF、DOC、DOCX 格式报告")

    raw_bytes = await file.read()
    file_size = len(raw_bytes)
    await file.seek(0)
    if file_size <= 0:
        raise HTTPException(status_code=422, detail="上传文件为空")
    if file_size > settings.MAX_FILE_SIZE:
        raise HTTPException(status_code=422, detail="文件过大，请控制在 100MB 以内")

    file_path = await storage_service.save_upload_file(file, patient_id)
    report = PatientReport(
        patient_id=str(patient_id),
        file_name=file_name,
        file_path=file_path,
        content_type=file.content_type,
        file_size=file_size,
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)

    return PatientReportInDB(
        id=report.id,
        patient_id=report.patient_id,
        file_name=report.file_name,
        file_path=report.file_path,
        content_type=report.content_type,
        file_size=report.file_size,
        uploaded_at=report.uploaded_at,
        download_url=_report_download_url(report.file_path),
    )


@router.delete("/{patient_id}/reports/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_patient_report(
    patient_id: UUID,
    report_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """删除患者病例报告"""
    query = select(PatientReport).where(
        PatientReport.id == str(report_id),
        PatientReport.patient_id == str(patient_id),
    )
    result = await db.execute(query)
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")

    storage_service.delete_file(report.file_path)
    await db.delete(report)
    await db.commit()
    return None
