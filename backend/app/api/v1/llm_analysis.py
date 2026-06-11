"""
LLM分析API
"""

from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import Dict, Any

from app.core.database import get_db
from app.models.examination import Examination
from app.schemas.examination import DoctorReviewUpdate, AnalysisRequest, LLMModelOption
from app.services.llm_service import llm_service
from app.services.report_service import report_service
from app.services.storage_service import storage_service

router = APIRouter()


@router.get("/models", response_model=list[LLMModelOption])
async def list_llm_models():
    return llm_service.list_models()


@router.post("/analyze/{examination_id}", response_model=Dict[str, Any])
async def analyze_examination(
    examination_id: str,
    request_data: AnalysisRequest | None = None,
    db: AsyncSession = Depends(get_db)
):
    """对检查记录执行LLM分析"""
    # 获取检查记录（含关联）
    query = select(Examination).where(Examination.id == examination_id).options(
        selectinload(Examination.polyps),
        selectinload(Examination.patient),
    )
    result = await db.execute(query)
    examination = result.scalar_one_or_none()
    if not examination:
        raise HTTPException(status_code=404, detail="检查记录不存在")

    patient = examination.patient

    # 准备息肉数据
    polyp_list = []
    for p in examination.polyps:
        polyp_list.append({
            "number": p.polyp_number,
            "size_mm": float(p.size_mm or 0),
            "shape_type": p.shape_type,
            "boundary_score": float(p.boundary_score or 0),
            "confidence": float(p.confidence_score or 0.9),
        })

    llm_input = {
        "patient_info": {
            "age": patient.age if patient else None,
            "gender": patient.gender if patient else None,
            "medical_history": patient.medical_history if patient else None,
        },
        "polyp_count": examination.polyp_count,
        "polyps": polyp_list,
        "image_quality": "良好",
        "clinical_notes": examination.doctor_notes,
        "history_examinations": await _load_history_examinations(db, examination.patient_id, examination.id),
    }

    requested_model_key = request_data.llm_model_key if request_data else None

    if requested_model_key:
        try:
            selected_model = llm_service.get_model_option(requested_model_key)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
    else:
        selected_model = llm_service.get_model_option(None) if llm_service.get_default_model_key() else None

    if not llm_service.is_available(requested_model_key):
        # 没有LLM API时生成规则引擎默认结果
        mock_result = _generate_rule_based_analysis(llm_input)
        examination.risk_level = mock_result["risk_level"]
        examination.pathology_type = mock_result["pathology_type"]
        examination.recommended_followup = mock_result["recommended_followup_days"]
        examination.llm_analysis = mock_result["analysis"]
        examination.llm_model_key = selected_model["key"] if selected_model else None
        examination.llm_model_id = selected_model["model_id"] if selected_model else None
        await db.commit()
        return {"success": True, "source": "rule_engine", **mock_result, **(selected_model or {})}

    analysis_result = await run_in_threadpool(
        llm_service.analyze_examination,
        llm_input,
        requested_model_key,
    )
    if not analysis_result["success"]:
        raise HTTPException(status_code=504, detail=analysis_result.get("message", "LLM分析超时或失败，请稍后重试"))

    if analysis_result["success"]:
        examination.risk_level = analysis_result["risk_level"]
        examination.pathology_type = analysis_result["pathology_type"]
        examination.recommended_followup = analysis_result["recommended_followup_days"]
        examination.llm_analysis = analysis_result["analysis"]
        examination.llm_model_key = analysis_result.get("llm_model_key")
        examination.llm_model_id = analysis_result.get("llm_model_id")
        await db.commit()

    return analysis_result


async def _load_history_examinations(db: AsyncSession, patient_id: str, current_examination_id: str) -> list[dict]:
    history_query = (
        select(Examination)
        .where(
            Examination.patient_id == patient_id,
            Examination.id != current_examination_id,
        )
        .order_by(Examination.exam_date.desc())
        .limit(5)
        .options(selectinload(Examination.polyps))
    )
    history_result = await db.execute(history_query)
    history_examinations = history_result.scalars().all()
    serialized = []
    for exam in history_examinations:
        sizes = [float(p.size_mm or 0) for p in exam.polyps]
        serialized.append({
            "examination_id": exam.id,
            "exam_date": exam.exam_date.isoformat() if exam.exam_date else None,
            "polyp_count": exam.polyp_count or 0,
            "risk_level": exam.risk_level,
            "pathology_type": exam.pathology_type,
            "max_size_mm": max(sizes) if sizes else 0.0,
            "doctor_notes": exam.doctor_notes,
            "clinical_report": (exam.llm_analysis or {}).get("clinical_report"),
            "historical_comparison": (exam.llm_analysis or {}).get("historical_comparison"),
            "progression_assessment": (exam.llm_analysis or {}).get("progression_assessment"),
            "doctor_confirmed_report": exam.doctor_confirmed_report,
            "doctor_reviewed_at": exam.doctor_reviewed_at.isoformat() if exam.doctor_reviewed_at else None,
        })
    return serialized


def _generate_rule_based_analysis(data: dict) -> dict:
    """规则引擎生成基础分析（LLM不可用时的降级方案）"""
    polyp_count = data.get("polyp_count", 0)
    polyps = data.get("polyps", [])
    patient_info = data.get("patient_info", {})
    age = patient_info.get("age", 50)
    history_examinations = data.get("history_examinations") or []
    latest_history = history_examinations[0] if history_examinations else {}
    previous_polyp_count = int(latest_history.get("polyp_count", 0) or 0)

    # 简单风险规则
    max_size = max((p.get("size_mm", p.get("diameter_mm", 0)) for p in polyps), default=0)
    if polyp_count == 0:
        risk_level = "low"
        followup_days = 365
        pathology_type = "未发现息肉"
    elif max_size >= 10 or polyp_count >= 3:
        risk_level = "high"
        followup_days = 90
        pathology_type = "腺瘤性息肉（可能）"
    elif max_size >= 6 or polyp_count >= 2:
        risk_level = "medium"
        followup_days = 180
        pathology_type = "增生性息肉（可能）"
    else:
        risk_level = "low"
        followup_days = 365
        pathology_type = "炎症性息肉（可能）"

    risk_label = {"high": "高", "medium": "中", "low": "低"}[risk_level]
    historical_comparison = "暂无可用于量化对比的历史检查记录。"
    progression_assessment = "缺少历史对照，建议后续连续随访以评估进展趋势。"
    if history_examinations:
        previous_max_size = float(latest_history.get("max_size_mm", 0) or 0)
        count_delta = polyp_count - previous_polyp_count
        size_delta = float(max_size) - previous_max_size
        historical_comparison = (
            f"与最近一次检查相比，息肉数量变化 {count_delta:+d}（本次 {polyp_count} 枚，上次 {previous_polyp_count} 枚），"
            f"最大直径变化 {size_delta:+.1f}mm（本次 {float(max_size):.1f}mm，上次 {previous_max_size:.1f}mm）。"
        )
        if count_delta > 0 or size_delta > 0.5:
            progression_assessment = "提示存在进展趋势（数量或体积增加），建议缩短复查间隔并加强干预。"
        elif count_delta < 0 and size_delta < -0.5:
            progression_assessment = "较既往呈改善趋势，建议继续规范随访。"
        else:
            progression_assessment = "与既往相比整体相对稳定，建议按计划随访。"

    analysis = {
        "risk_level": risk_level,
        "pathology_type": pathology_type,
        "recommended_followup_days": followup_days,
        "treatment_recommendation": "建议结合病理结果决定是否进行内镜下切除及进一步随访管理。",
        "key_findings": [
            f"息肉数量：{polyp_count} 枚",
            f"最大直径：{max_size:.1f} mm",
            f"风险分层：{risk_label}风险",
        ],
        "risk_factors": [
            "息肉数量和大小提示需要规律随访",
            "最终病理诊断需以组织学检查为准",
        ],
        "doctor_explanation": (
            f"本次结肠镜检查发现息肉 {polyp_count} 枚，"
            f"最大直径约 {max_size:.1f}mm。"
            f"风险评级：{risk_label}风险。"
            f"建议 {followup_days} 天后复查结肠镜。"
        ),
        "patient_explanation": (
            f"这次检查共发现了 {polyp_count} 个息肉。"
            f"医生评估为{risk_label}风险。"
            f"请在 {followup_days // 30} 个月内进行复查。"
            "保持健康饮食，减少高脂肪食物摄入。"
        ),
        "treatment_suggestions": [
            "定期随访，复查结肠镜",
            "保持健康体重，规律运动",
            "减少红肉和加工肉类摄入",
            "增加膳食纤维摄入",
        ] if polyp_count > 0 else ["继续保持健康生活方式"],
        "dietary_advice": [
            "多吃蔬菜水果，增加膳食纤维",
            "减少油腻、辛辣食物",
            "戒烟限酒",
            "每天保持 30 分钟以上中等强度运动",
        ],
        "followup_plan": f"建议 {followup_days} 天（约 {followup_days // 30} 个月）后复查结肠镜。如有腹部不适、便血等症状应立即就医。",
        "clinical_report": (
            f"【检查综述】本次检查共识别息肉 {polyp_count} 枚，最大直径约 {max_size:.1f}mm。"
            f"【风险评估】当前为{risk_label}风险，病理倾向为{pathology_type}。"
            f"【处置建议】建议结合病理结果评估是否内镜下切除，并在 {followup_days} 天后复查。"
            "【生活方式】建议规律运动、戒烟限酒并优化饮食结构。"
        ),
        "historical_comparison": historical_comparison,
        "progression_assessment": progression_assessment,
    }

    return {
        "success": True,
        "risk_level": risk_level,
        "pathology_type": pathology_type,
        "recommended_followup_days": followup_days,
        "analysis": analysis,
    }


@router.get("/report/{examination_id}", response_model=Dict[str, Any])
async def get_report(
    examination_id: str,
    db: AsyncSession = Depends(get_db)
):
    """获取检查分析报告"""
    examination = await db.get(Examination, examination_id)
    if not examination:
        raise HTTPException(status_code=404, detail="检查记录不存在")

    return {
        "examination_id": examination_id,
        "risk_level": examination.risk_level,
        "pathology_type": examination.pathology_type,
        "recommended_followup": examination.recommended_followup,
        "llm_analysis": examination.llm_analysis,
        "llm_model_key": examination.llm_model_key,
        "llm_model_id": examination.llm_model_id,
        "doctor_confirmed_report": examination.doctor_confirmed_report,
        "doctor_reviewed": bool(examination.doctor_reviewed),
        "doctor_reviewed_at": examination.doctor_reviewed_at.isoformat() if examination.doctor_reviewed_at else None,
    }


@router.put("/report/{examination_id}/doctor-review", response_model=Dict[str, Any])
async def update_doctor_review(
    examination_id: str,
    review_data: DoctorReviewUpdate,
    db: AsyncSession = Depends(get_db)
):
    examination = await db.get(Examination, examination_id)
    if not examination:
        raise HTTPException(status_code=404, detail="检查记录不存在")

    payload = review_data.model_dump()
    now = datetime.now()
    examination.doctor_confirmed_report = payload
    examination.doctor_reviewed = True
    examination.doctor_reviewed_at = now
    examination.risk_level = payload["risk_level"]
    examination.pathology_type = payload["pathology_type"]
    if examination.llm_analysis:
        examination.llm_analysis = {**examination.llm_analysis, **payload}
    else:
        examination.llm_analysis = payload
    await db.commit()
    await db.refresh(examination)

    return {
        "success": True,
        "examination_id": examination.id,
        "doctor_confirmed_report": examination.doctor_confirmed_report,
        "doctor_reviewed": bool(examination.doctor_reviewed),
        "doctor_reviewed_at": examination.doctor_reviewed_at.isoformat() if examination.doctor_reviewed_at else None,
    }


@router.get("/report/{examination_id}/download")
async def download_confirmed_report(
    examination_id: str,
    db: AsyncSession = Depends(get_db)
):
    query = select(Examination).where(Examination.id == examination_id).options(
        selectinload(Examination.patient)
    )
    result = await db.execute(query)
    examination = result.scalar_one_or_none()
    if not examination:
        raise HTTPException(status_code=404, detail="检查记录不存在")
    if not examination.doctor_reviewed or not examination.doctor_confirmed_report:
        raise HTTPException(status_code=409, detail="请先完成医生审核与确认后再下载正式报告")

    patient = examination.patient
    model_label = "未记录"
    if examination.llm_model_key:
        registry_item = next((item for item in llm_service.list_models() if item["key"] == examination.llm_model_key), None)
        if registry_item:
            model_label = str(registry_item["label"])

    source_image_path = _resolve_local_report_image(examination.image_path)
    segmentation_image_path = _resolve_local_report_image(examination.result_path)

    pdf_bytes = report_service.build_confirmed_report_pdf(
        patient_name=patient.name if patient else "未填写",
        patient_gender=patient.gender if patient else None,
        patient_age=patient.age if patient else None,
        patient_phone=patient.phone if patient else None,
        examination_id=examination.id,
        exam_date=examination.exam_date,
        exam_type=examination.exam_type,
        model_label=model_label,
        confirmed_report=examination.doctor_confirmed_report,
        reviewed_at=examination.doctor_reviewed_at,
        doctor_name="张医师",
        source_image_path=source_image_path,
        segmentation_image_path=segmentation_image_path,
    )

    exam_date_text = examination.exam_date.strftime("%Y%m%d") if examination.exam_date else "unknown"
    patient_name = patient.name if patient and patient.name else "患者"
    filename = f"{patient_name}_{exam_date_text}_确认版报告.pdf"
    encoded_filename = quote(filename)
    headers = {
        "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
    }
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers=headers,
    )


def _resolve_local_report_image(file_path: str | None) -> str | None:
    if not file_path or file_path.startswith("minio://"):
        return None

    absolute_path = (storage_service.local_storage_path / Path(file_path)).resolve()
    if absolute_path.exists() and absolute_path.is_file():
        return str(absolute_path)
    return None
