"""
检查管理API
提供图像上传、分割、结果查询等功能
"""

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, status, BackgroundTasks, Form
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload
from typing import List, Optional
from uuid import UUID
import os
from datetime import datetime
from pathlib import Path
from starlette.concurrency import run_in_threadpool

from app.core.database import get_db
from app.models.examination import Examination
from app.models.polyp import Polyp
from app.schemas.examination import ExaminationCreate, ExaminationInDB, ExaminationList
import app.services.model_service as model_service_module
from app.services.llm_service import llm_service
from app.services.storage_service import storage_service
from app.utils.image_processor import ImageProcessor

router = APIRouter()


@router.post("/upload", response_model=ExaminationInDB, status_code=status.HTTP_201_CREATED)
async def upload_examination(
    patient_id: UUID,
    file: UploadFile = File(...),
    clinical_notes: Optional[str] = Form(None),
    llm_model_key: Optional[str] = Form(None),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_db)
):
    """
    上传检查图像并执行分割

    流程:
    1. 保存上传的文件
    2. 执行BFNet模型分割
    3. 提取息肉信息
    4. 调用LLM进行分析 (后台任务)
    5. 保存到数据库
    """
    patient_id_str = str(patient_id)
    selected_model = None
    if llm_model_key:
        try:
            selected_model = llm_service.get_model_option(llm_model_key)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
    elif llm_service.get_default_model_key():
        selected_model = llm_service.get_model_option(None)

    # 验证患者是否存在
    from app.models.patient import Patient
    patient = await db.get(Patient, patient_id_str)
    if not patient:
        raise HTTPException(status_code=404, detail="患者不存在")

    # 保存上传的文件
    try:
        file_path = await storage_service.save_upload_file(file, patient_id_str)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件保存失败: {str(e)}")

    source_file_path = file_path
    if not file_path.startswith("minio://"):
        source_file_path = str(storage_service.local_storage_path / Path(file_path))

    # 读取并处理图像
    try:
        image_processor = ImageProcessor()
        image = await image_processor.read_image(source_file_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"图像读取失败: {str(e)}")

    # 执行模型分割
    if model_service_module.model_service.model is None:
        # 模型未加载时，使用模拟数据
        import numpy as np
        segmentation_result = {
            "success": True,
            "mask": np.zeros((image.shape[0], image.shape[1]), dtype=np.uint8),
            "polyp_count": 0,
            "polyps": [],
            "message": "模型未加载，跳过分割（演示模式）"
        }
    else:
        segmentation_result = model_service_module.model_service.predict(image)

    if not segmentation_result["success"]:
        raise HTTPException(status_code=500, detail=segmentation_result["message"])

    history_query = (
        select(Examination)
        .where(Examination.patient_id == patient_id_str)
        .order_by(desc(Examination.exam_date))
        .limit(5)
        .options(selectinload(Examination.polyps))
    )
    history_result = await db.execute(history_query)
    history_examinations = _serialize_history_examinations(history_result.scalars().all())

    # 保存分割结果图像
    result_path = None
    if model_service_module.model_service.model is not None:
        try:
            mask = segmentation_result["mask"]
            result_image = model_service_module.model_service.visualize_result(image, mask, segmentation_result["polyps"])
            result_path = await storage_service.save_segmentation_result(
                result_image, patient_id_str, file.filename
            )
        except Exception as e:
            print(f"分割结果保存失败: {e}")

    # 创建检查记录
    examination = Examination(
        patient_id=patient_id_str,
        exam_date=datetime.now(),
        exam_type="colonoscopy",
        image_path=file_path,
        result_path=result_path,
        polyp_count=segmentation_result["polyp_count"],
        risk_level="pending",
        doctor_notes=(clinical_notes.strip() if clinical_notes and clinical_notes.strip() else None),
        llm_model_key=selected_model["key"] if selected_model else None,
        llm_model_id=selected_model["model_id"] if selected_model else None,
    )

    db.add(examination)
    await db.flush()

    # 保存息肉详情
    for polyp_data in segmentation_result["polyps"]:
        polyp = Polyp(
            examination_id=examination.id,
            polyp_number=polyp_data["number"],
            location="待标注",
            size_mm=polyp_data["diameter_mm"],
            boundary_score=polyp_data["boundary_score"],
            shape_type=polyp_data["shape_type"],
            confidence_score=polyp_data["confidence"],
            bbox_coords=polyp_data["bbox"],
        )
        db.add(polyp)

    await db.commit()
    await db.refresh(examination)

    # 后台执行LLM分析
    if background_tasks and llm_service.is_available():
        background_tasks.add_task(
            perform_llm_analysis,
            examination.id,
            patient,
            segmentation_result,
            clinical_notes,
            history_examinations,
            selected_model["key"] if selected_model else None,
        )

    return examination


async def perform_llm_analysis(
    examination_id: UUID,
    patient,
    segmentation_result: dict,
    clinical_notes: Optional[str] = None,
    history_examinations: Optional[List[dict]] = None,
    llm_model_key: Optional[str] = None,
    db: AsyncSession = None
):
    """后台执行LLM分析任务"""
    if db is None:
        from app.core.database import AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            await _perform_llm_analysis_internal(examination_id, patient, segmentation_result, clinical_notes, history_examinations, llm_model_key, session)
    else:
        await _perform_llm_analysis_internal(examination_id, patient, segmentation_result, clinical_notes, history_examinations, llm_model_key, db)


async def _perform_llm_analysis_internal(
    examination_id: UUID,
    patient,
    segmentation_result: dict,
    clinical_notes: Optional[str],
    history_examinations: Optional[List[dict]],
    llm_model_key: Optional[str],
    db: AsyncSession
):
    """执行LLM分析的实现"""
    try:
        examination_data = {
            "patient_info": {
                "age": patient.age,
                "gender": patient.gender,
                "medical_history": patient.medical_history,
            },
            "polyp_count": segmentation_result["polyp_count"],
            "polyps": segmentation_result["polyps"],
            "image_quality": "良好",
            "clinical_notes": clinical_notes,
            "history_examinations": history_examinations or [],
        }

        analysis_result = await run_in_threadpool(
            llm_service.analyze_examination,
            examination_data,
            llm_model_key,
        )

        if analysis_result["success"]:
            examination = await db.get(Examination, str(examination_id))
            if examination:
                model_key = analysis_result.get("llm_model_key")
                model_id = analysis_result.get("llm_model_id")
                examination.risk_level = analysis_result["risk_level"]
                examination.pathology_type = analysis_result["pathology_type"]
                examination.recommended_followup = analysis_result["recommended_followup_days"]
                examination.llm_analysis = analysis_result["analysis"]
                examination.llm_model_key = model_key
                examination.llm_model_id = model_id

                from app.models.followup import FollowupPlan
                from datetime import timedelta

                followup_date = datetime.now() + timedelta(days=analysis_result["recommended_followup_days"])
                followup_plan = FollowupPlan(
                    patient_id=examination.patient_id,
                    examination_id=str(examination_id),
                    next_exam_date=followup_date,
                    notes=f"基于LLM分析自动生成: {analysis_result['risk_level']}风险等级",
                )
                db.add(followup_plan)
                await db.commit()
                print(f"LLM分析完成: {examination_id}")
        else:
            print(f"LLM分析失败: {analysis_result.get('message')}")

    except Exception as e:
        print(f"LLM分析任务异常: {str(e)}")


def _serialize_history_examinations(examinations: List[Examination]) -> List[dict]:
    serialized = []
    for exam in examinations:
        polyp_sizes = [float(p.size_mm or 0) for p in exam.polyps]
        serialized.append({
            "examination_id": exam.id,
            "exam_date": exam.exam_date.isoformat() if exam.exam_date else None,
            "polyp_count": exam.polyp_count or 0,
            "risk_level": exam.risk_level,
            "pathology_type": exam.pathology_type,
            "max_size_mm": max(polyp_sizes) if polyp_sizes else 0.0,
            "doctor_notes": exam.doctor_notes,
            "clinical_report": (exam.llm_analysis or {}).get("clinical_report"),
            "historical_comparison": (exam.llm_analysis or {}).get("historical_comparison"),
            "progression_assessment": (exam.llm_analysis or {}).get("progression_assessment"),
            "doctor_confirmed_report": exam.doctor_confirmed_report,
            "doctor_reviewed_at": exam.doctor_reviewed_at.isoformat() if exam.doctor_reviewed_at else None,
        })
    return serialized


@router.get("/", response_model=List[ExaminationList])
async def list_examinations(
    patient_id: Optional[UUID] = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """获取检查记录列表"""
    query = select(Examination).order_by(desc(Examination.exam_date))

    if patient_id:
        query = query.where(Examination.patient_id == str(patient_id))

    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    examinations = result.scalars().all()

    return examinations


@router.get("/{examination_id}", response_model=ExaminationInDB)
async def get_examination(
    examination_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """获取单个检查的详细信息"""
    query = select(Examination).where(Examination.id == str(examination_id)).options(
        selectinload(Examination.polyps)
    )
    result = await db.execute(query)
    examination = result.scalar_one_or_none()
    if not examination:
        raise HTTPException(status_code=404, detail="检查记录不存在")

    return examination


@router.delete("/{examination_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_examination(
    examination_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """删除检查记录"""
    examination = await db.get(Examination, str(examination_id))
    if not examination:
        raise HTTPException(status_code=404, detail="检查记录不存在")

    if examination.image_path and not examination.image_path.startswith("minio://"):
        image_local_path = storage_service.local_storage_path / Path(examination.image_path)
        if image_local_path.exists():
            os.remove(image_local_path)
    if examination.result_path and not examination.result_path.startswith("minio://"):
        result_local_path = storage_service.local_storage_path / Path(examination.result_path)
        if result_local_path.exists():
            os.remove(result_local_path)

    await db.delete(examination)
    await db.commit()

    return None
