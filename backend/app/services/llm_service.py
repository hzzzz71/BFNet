"""
LLM医学知识增强服务
调用兼容 OpenAI 接口的模型生成风险评估、病理预测和治疗建议
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Dict, List, Optional

from openai import OpenAI

from app.core.config import settings


@dataclass(frozen=True)
class LLMModelConfig:
    key: str
    label: str
    provider: str
    model_id: str
    api_key: str
    base_url: str

    @property
    def available(self) -> bool:
        return bool(self.api_key and self.model_id)


class LLMService:
    """LLM医学分析服务"""

    def __init__(self):
        self.model_registry = self._build_model_registry()
        self.default_model_key = self._resolve_default_model_key()
        print(f"LLM模型注册完成，默认模型: {self.default_model_key or '未配置'}")

    def _build_model_registry(self) -> Dict[str, LLMModelConfig]:
        deepseek_api_key = settings.DEEPSEEK_API_KEY or settings.OPENAI_API_KEY
        deepseek_base_url = (settings.DEEPSEEK_BASE_URL or settings.OPENAI_BASE_URL or "https://api.deepseek.com").rstrip("/")
        siliconflow_base_url = (settings.SILICONFLOW_BASE_URL or "https://api.siliconflow.cn/v1").rstrip("/")

        return {
            "deepseek_chat": LLMModelConfig(
                key="deepseek_chat",
                label="DeepSeek Chat",
                provider="deepseek",
                model_id=settings.DEEPSEEK_MODEL or settings.OPENAI_MODEL or "deepseek-chat",
                api_key=deepseek_api_key,
                base_url=deepseek_base_url,
            ),
            "kimi_k2_6": LLMModelConfig(
                key="kimi_k2_6",
                label="Kimi K2.6",
                provider="siliconflow",
                model_id=settings.SILICONFLOW_KIMI_MODEL_ID,
                api_key=settings.SILICONFLOW_API_KEY,
                base_url=siliconflow_base_url,
            ),
            "glm_5_1": LLMModelConfig(
                key="glm_5_1",
                label="GLM 5.1",
                provider="siliconflow",
                model_id=settings.SILICONFLOW_GLM_MODEL_ID,
                api_key=settings.SILICONFLOW_API_KEY,
                base_url=siliconflow_base_url,
            ),
        }

    def _resolve_default_model_key(self) -> Optional[str]:
        configured_default = settings.DEFAULT_LLM_MODEL_KEY
        if configured_default in self.model_registry and self.model_registry[configured_default].available:
            return configured_default

        for key, config in self.model_registry.items():
            if config.available:
                return key
        return None

    def list_models(self) -> List[Dict[str, object]]:
        default_key = self.get_default_model_key()
        return [
            {
                "key": config.key,
                "label": config.label,
                "provider": config.provider,
                "available": config.available,
                "default": config.key == default_key,
            }
            for config in self.model_registry.values()
        ]

    def get_default_model_key(self) -> Optional[str]:
        return self._resolve_default_model_key()

    def is_available(self, model_key: Optional[str] = None) -> bool:
        try:
            self.resolve_model_config(model_key)
            return True
        except ValueError:
            return False

    def resolve_model_config(self, model_key: Optional[str] = None) -> LLMModelConfig:
        key = model_key or self.get_default_model_key()
        if not key:
            raise ValueError("当前未配置可用的 LLM 模型")

        config = self.model_registry.get(key)
        if config is None:
            raise ValueError(f"不支持的模型选择: {key}")
        if not config.available:
            raise ValueError(f"模型 {config.label} 当前不可用，请检查 API Key 或模型 ID 配置")
        return config

    def get_model_option(self, model_key: Optional[str]) -> Dict[str, object]:
        config = self.resolve_model_config(model_key)
        return {
            "key": config.key,
            "label": config.label,
            "provider": config.provider,
            "model_id": config.model_id,
        }

    def _build_client(self, config: LLMModelConfig) -> OpenAI:
        base_url = config.base_url
        if not base_url.endswith("/v1"):
            base_url = f"{base_url}/v1"
        return OpenAI(
            api_key=config.api_key,
            base_url=base_url,
            timeout=settings.LLM_TIMEOUT_SECONDS,
        )

    def analyze_examination(self, examination_data: Dict, model_key: Optional[str] = None) -> Dict:
        """
        对检查结果进行全面的LLM分析
        """
        try:
            model_config = self.resolve_model_config(model_key)
        except ValueError as exc:
            return {
                "success": False,
                "message": str(exc),
                "risk_level": "unknown",
                "analysis": {},
            }

        try:
            prompt = self._build_analysis_prompt(examination_data)
            client = self._build_client(model_config)
            response = client.chat.completions.create(
                model=model_config.model_id,
                messages=[
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user", "content": prompt},
                ],
                temperature=settings.LLM_TEMPERATURE,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            raw_analysis_result = json.loads(content)
            analysis_result = self._normalize_analysis_result(raw_analysis_result, examination_data)
            analysis_result["llm_model_key"] = model_config.key
            analysis_result["llm_model_id"] = model_config.model_id
            analysis_result["llm_model_label"] = model_config.label
            analysis_result["llm_provider"] = model_config.provider
            explanations = self._generate_explanations(analysis_result)

            return {
                "success": True,
                "risk_level": analysis_result["risk_level"],
                "pathology_type": analysis_result["pathology_type"],
                "recommended_followup_days": analysis_result["recommended_followup_days"],
                "treatment_recommendation": analysis_result["treatment_recommendation"],
                "key_findings": analysis_result["key_findings"],
                "explanations": explanations,
                "analysis": analysis_result,
                "llm_model_key": model_config.key,
                "llm_model_id": model_config.model_id,
                "llm_model_label": model_config.label,
                "llm_provider": model_config.provider,
            }
        except Exception as exc:
            return {
                "success": False,
                "message": f"LLM分析失败: {str(exc)}",
                "risk_level": "unknown",
                "analysis": {},
            }

    def _get_polyp_size_mm(self, polyp: Dict) -> float:
        size = polyp.get("size_mm")
        if size is None:
            size = polyp.get("diameter_mm")
        try:
            return float(size or 0)
        except (TypeError, ValueError):
            return 0.0

    def _build_analysis_prompt(self, data: Dict) -> str:
        """构建分析prompt"""
        patient = data.get("patient_info", {})
        polyps = data.get("polyps", [])
        clinical_notes = (data.get("clinical_notes") or "").strip()
        clinical_context_hint = self._build_clinical_context_summary(clinical_notes)
        history_examinations = data.get("history_examinations") or []

        prompt = f"""请作为一位经验丰富的消化内科医生，分析以下结肠镜检查报告并给出专业建议。

患者信息:
- 年龄: {patient.get('age', '未知')}
- 性别: {patient.get('gender', '未知')}
- 既往病史: {patient.get('medical_history', '无特殊')}

检查结果:
- 息肉数量: {len(polyps)}个
- 图像质量: {data.get('image_quality', '良好')}

息肉详情:
"""

        for idx, polyp in enumerate(polyps, 1):
            polyp_size_mm = self._get_polyp_size_mm(polyp)
            prompt += f"""
息肉 #{idx}:
- 位置: {polyp.get('location', '未标注')}
- 大小: {polyp_size_mm:.1f}mm
- 形态: {polyp.get('shape_type', 'unknown')}
- 边界清晰度: {polyp.get('boundary_score', 0):.2f}
"""

        if clinical_notes:
            prompt += f"""

门诊补充信息:
{clinical_notes}

门诊补充信息提炼（供参考）:
{clinical_context_hint}
"""

        if history_examinations:
            prompt += """

历史检查对比信息:
"""
            for idx, exam in enumerate(history_examinations, 1):
                confirmed_report = exam.get("doctor_confirmed_report") or {}
                historical_report_text = confirmed_report.get("clinical_report") or exam.get("clinical_report") or "无"
                historical_treatment = confirmed_report.get("treatment_recommendation") or exam.get("doctor_notes") or "无"
                historical_progression = confirmed_report.get("progression_assessment") or exam.get("progression_assessment") or "无"
                prompt += f"""
历史检查 #{idx}:
- 检查日期: {exam.get('exam_date', '未知')}
- 息肉数量: {exam.get('polyp_count', 0)}个
- 最大直径: {float(exam.get('max_size_mm', 0) or 0):.1f}mm
- 风险等级: {exam.get('risk_level', '未知')}
- 病理类型: {exam.get('pathology_type', '未知')}
- 医生备注: {exam.get('doctor_notes', '无')}
- 历史报告摘要: {historical_report_text}
- 历史处置结论: {historical_treatment}
- 历史进展评估: {historical_progression}
"""

        prompt += """

请按照以下JSON格式输出分析结果:
{
  "risk_level": "low|medium|high",
  "pathology_type": "预测的病理类型(腺瘤性/炎性/增生性等)",
  "recommended_followup_days": 建议复查天数(整数),
  "treatment_recommendation": "详细的治疗建议",
  "key_findings": ["关键发现1", "关键发现2", ...],
  "risk_factors": ["风险因素1", "风险因素2", ...],
  "doctor_explanation": "给临床医生看的专业解释",
  "patient_explanation": "给患者看的通俗解释",
  "treatment_suggestions": ["建议1", "建议2", ...],
  "dietary_advice": ["饮食建议1", "饮食建议2", ...],
  "followup_plan": "随访方案文字",
  "clinical_report": "完整文字版检查说明报告（分段描述风险判断依据、病理倾向、处置建议和注意事项）",
  "clinical_context_summary": "门诊问诊/症状/临床判断对本次风险与处置建议的影响总结（提炼版，不要原文复述）",
  "historical_comparison": "与既往检查对比结论，明确数量/大小/风险变化趋势",
  "progression_assessment": "进展评估，如增多、增大、稳定或好转"
}

风险评估标准:
- low: 0-1个小息肉(<5mm),边界清晰
- medium: 2-3个息肉或单个较大息肉(5-10mm)
- high: >3个息肉,或息肉>10mm,或边界不清,或形态不规则

请严格结合历史检查信息（含历史报告摘要）和门诊补充信息进行判断，明确比较“数量变化、体积变化、风险变化、病理倾向变化”。
特别要求：
1) clinical_context_summary 必须解释门诊信息如何影响风险判断或处置建议；
2) clinical_report 不要逐字复制门诊补充信息原文，应做医学提炼；
3) 如门诊信息与图像结果存在冲突，请指出冲突并给出处理优先级。
并遵循上述JSON格式，不要添加任何其他说明。"""

        return prompt

    def _get_system_prompt(self) -> str:
        return """你是一位经验丰富的消化内科医生，专门负责分析结肠镜检查结果。

你的任务是:
1. 根据息肉的数量、大小、形态、边界清晰度评估风险等级
2. 预测可能的病理类型(腺瘤性、炎性、增生性等)
3. 给出个性化的复查建议
4. 提供详细的治疗方案建议
5. 列出关键发现和风险因素

请始终保持客观、专业，基于医学证据给出建议。"""

    def _generate_explanations(self, analysis_result: Dict) -> Dict[str, str]:
        risk_level = analysis_result.get("risk_level", "unknown")
        pathology_type = analysis_result.get("pathology_type", "未知")
        followup_days = analysis_result.get("recommended_followup_days", 365)
        treatment = analysis_result.get("treatment_recommendation", "")

        doctor_explanation = f"""风险等级: {risk_level.upper()}
预测病理类型: {pathology_type}
建议复查周期: {followup_days}天
治疗建议: {treatment}

关键发现:
""" + "\n".join(analysis_result.get("key_findings", []))

        risk_desc = {
            "low": "低风险",
            "medium": "中等风险",
            "high": "高风险",
            "unknown": "风险未知",
        }

        patient_explanation = f"""根据您的检查结果，您的息肉风险等级为: {risk_desc.get(risk_level, '未知')}

我们预测您的息肉类型可能是: {pathology_type}

{self._get_patient_guidance(risk_level, followup_days)}

医生为您制定的治疗建议是:
{treatment}

重要提示:
""" + "\n".join([f"• {finding}" for finding in analysis_result.get("key_findings", [])])

        return {
            "doctor_version": doctor_explanation,
            "patient_version": patient_explanation,
        }

    def _normalize_analysis_result(self, analysis_result: Dict, examination_data: Dict) -> Dict:
        polyps = examination_data.get("polyps", [])
        polyp_count = examination_data.get("polyp_count", len(polyps))
        max_size = max((self._get_polyp_size_mm(p) for p in polyps), default=0.0)
        risk_level = analysis_result.get("risk_level", "unknown")
        pathology_type = analysis_result.get("pathology_type", "未知")
        followup_days = int(analysis_result.get("recommended_followup_days", 365) or 365)
        treatment_recommendation = analysis_result.get("treatment_recommendation", "请结合临床与病理检查结果进行个体化治疗决策。")
        key_findings = analysis_result.get("key_findings") or []
        risk_factors = analysis_result.get("risk_factors") or []
        doctor_explanation = analysis_result.get("doctor_explanation", "").strip()
        patient_explanation = analysis_result.get("patient_explanation", "").strip()
        treatment_suggestions = analysis_result.get("treatment_suggestions") or []
        dietary_advice = analysis_result.get("dietary_advice") or []
        followup_plan = analysis_result.get("followup_plan", "").strip()
        clinical_report = analysis_result.get("clinical_report", "").strip()
        clinical_context_summary = analysis_result.get("clinical_context_summary", "").strip()
        historical_comparison = analysis_result.get("historical_comparison", "").strip()
        progression_assessment = analysis_result.get("progression_assessment", "").strip()
        clinical_notes = (examination_data.get("clinical_notes") or "").strip()
        history_examinations = examination_data.get("history_examinations") or []
        latest_history = history_examinations[0] if history_examinations else {}
        previous_polyp_count = int(latest_history.get("polyp_count", 0) or 0)
        previous_max_size = float(latest_history.get("max_size_mm", 0) or 0)
        count_delta = polyp_count - previous_polyp_count
        size_delta = max_size - previous_max_size

        if not doctor_explanation:
            doctor_explanation = (
                f"本次检查共识别息肉 {polyp_count} 枚，最大直径约 {max_size:.1f}mm。"
                f"综合数量、大小与形态特征评估为 {risk_level} 风险，病理倾向为 {pathology_type}。"
                f"建议约 {followup_days} 天后复查，并根据病理结果调整治疗路径。"
            )
        if not patient_explanation:
            patient_explanation = (
                f"这次检查发现了 {polyp_count} 个息肉，医生评估风险为 {risk_level}。"
                f"建议在 {followup_days} 天左右复查，并按医生建议进行后续处理。"
            )
        if not treatment_suggestions:
            treatment_suggestions = [
                treatment_recommendation,
                "建议结合病理结果与临床症状决定是否内镜切除或进一步治疗。",
                "如出现便血、腹痛或排便习惯明显变化，请尽快复诊。",
            ]
        if not dietary_advice:
            dietary_advice = [
                "增加膳食纤维摄入，保持规律排便。",
                "减少高脂肪和加工肉类摄入。",
                "保持规律运动，控制体重，戒烟限酒。",
            ]
        if not followup_plan:
            followup_plan = f"建议在 {followup_days} 天后复查结肠镜；若症状加重请提前复诊。"
        if not key_findings:
            key_findings = [
                f"息肉数量：{polyp_count} 枚",
                f"最大直径：{max_size:.1f} mm",
                f"风险等级：{risk_level}",
            ]
        if not risk_factors:
            risk_factors = [
                "息肉数量与最大直径是当前主要风险依据",
                "最终病理需结合术后组织学检查确认",
            ]
        if not clinical_report:
            findings_text = "；".join(key_findings)
            risk_factors_text = "；".join(risk_factors)
            treatment_text = "；".join(treatment_suggestions[:3])
            clinical_report = (
                f"【检查综述】本次结肠镜图像经分割识别后，共发现息肉 {polyp_count} 枚，最大直径约 {max_size:.1f}mm。"
                f"【风险评估】综合形态与大小特征，当前评估为 {risk_level} 风险，病理倾向为 {pathology_type}。"
                f"【关键发现】{findings_text}。"
                f"【风险因素】{risk_factors_text}。"
                f"【处置建议】{treatment_text}。"
                f"【随访建议】{followup_plan}"
            )
        if clinical_notes and not clinical_context_summary:
            clinical_context_summary = self._build_clinical_context_summary(clinical_notes)
        if clinical_notes and clinical_notes in clinical_report:
            clinical_report = clinical_report.replace(
                clinical_notes,
                "（门诊补充信息已用于综合判断，详见“临床信息整合”）",
            )
        if clinical_context_summary and "【临床信息整合】" not in clinical_report:
            clinical_report = f"{clinical_report}【临床信息整合】{clinical_context_summary}"
        if not historical_comparison:
            if history_examinations:
                historical_comparison = (
                    f"与最近一次检查相比，息肉数量变化 {count_delta:+d}（本次 {polyp_count} 枚，上次 {previous_polyp_count} 枚），"
                    f"最大直径变化 {size_delta:+.1f}mm（本次 {max_size:.1f}mm，上次 {previous_max_size:.1f}mm）。"
                )
            else:
                historical_comparison = "暂无可用于量化对比的历史检查记录。"
        if not progression_assessment:
            if history_examinations:
                if count_delta > 0 or size_delta > 0.5:
                    progression_assessment = "提示存在进展趋势（数量或体积增加），建议缩短复查间隔并加强干预。"
                elif count_delta < 0 and size_delta < -0.5:
                    progression_assessment = "较既往呈改善趋势，建议继续规范随访。"
                else:
                    progression_assessment = "与既往相比整体相对稳定，建议按计划随访。"
            else:
                progression_assessment = "缺少历史对照，建议后续连续随访以评估进展趋势。"
        return {
            "risk_level": risk_level,
            "pathology_type": pathology_type,
            "recommended_followup_days": followup_days,
            "treatment_recommendation": treatment_recommendation,
            "key_findings": key_findings,
            "risk_factors": risk_factors,
            "doctor_explanation": doctor_explanation,
            "patient_explanation": patient_explanation,
            "treatment_suggestions": treatment_suggestions,
            "dietary_advice": dietary_advice,
            "followup_plan": followup_plan,
            "clinical_report": clinical_report,
            "clinical_context_summary": clinical_context_summary,
            "historical_comparison": historical_comparison,
            "progression_assessment": progression_assessment,
        }

    def _build_clinical_context_summary(self, clinical_notes: str) -> str:
        notes = (clinical_notes or "").strip()
        if not notes:
            return ""
        merged = notes.replace("\r\n", "\n").replace("\r", "\n")
        sections = {"门诊问诊信息": "", "症状描述": "", "临床判断": ""}
        for line in merged.split("\n"):
            text = line.strip()
            if not text:
                continue
            matched = False
            for key in sections:
                prefix = f"{key}："
                if text.startswith(prefix):
                    sections[key] = text[len(prefix):].strip()
                    matched = True
                    break
            if not matched and not sections["门诊问诊信息"]:
                sections["门诊问诊信息"] = text
        pieces = []
        if sections["症状描述"]:
            pieces.append(f"症状提示：{sections['症状描述'][:120]}")
        if sections["临床判断"]:
            pieces.append(f"临床关注点：{sections['临床判断'][:120]}")
        if sections["门诊问诊信息"]:
            pieces.append(f"问诊要点：{sections['门诊问诊信息'][:120]}")
        if not pieces:
            pieces.append(f"门诊信息要点：{merged[:180]}")
        pieces.append("以上信息已与影像分割结果和历史检查共同用于风险分层与处置建议。")
        return "；".join(pieces)

    def _get_patient_guidance(self, risk_level: str, followup_days: int) -> str:
        if risk_level == "low":
            return f"""好消息！您的息肉风险较低，这通常意味着息肉是良性的可能性较大。
建议您在大约{followup_days}天后进行复查，以确保一切正常。
在此期间，请保持健康的生活方式，包括:
• 多吃蔬菜水果，减少红肉摄入
• 保持规律运动
• 避免吸烟和过量饮酒
"""
        if risk_level == "medium":
            return f"""您的息肉风险为中等，这意味着需要更加密切的随访。
建议您在大约{followup_days}天后进行复查，医生会根据复查结果决定是否需要进一步治疗。
请严格遵循医生的建议，并保持健康的生活方式。
"""
        if risk_level == "high":
            return f"""您的息肉风险较高，需要尽快与医生讨论治疗方案。
建议您在大约{followup_days}天内进行复查或治疗。
请不要过度担心，现代医学有很好的治疗方法。
请务必遵循医生的所有建议，并定期随访。
"""
        return f"""由于某些原因，我们无法确定您的风险等级。
建议您在大约{followup_days}天后进行复查，并与医生详细讨论检查结果。
"""

    def generate_followup_suggestion(self, patient_history: List[Dict], model_key: Optional[str] = None) -> Dict:
        try:
            model_config = self.resolve_model_config(model_key)
        except ValueError as exc:
            return {
                "success": False,
                "message": str(exc),
                "suggestion": "",
            }

        try:
            prompt = self._build_followup_prompt(patient_history)
            client = self._build_client(model_config)
            response = client.chat.completions.create(
                model=model_config.model_id,
                messages=[
                    {"role": "system", "content": "你是一位消化系统专科医生，负责制定患者随访计划。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=500,
            )
            suggestion = response.choices[0].message.content
            return {
                "success": True,
                "suggestion": suggestion,
                "llm_model_key": model_config.key,
                "llm_model_id": model_config.model_id,
                "llm_model_label": model_config.label,
            }
        except Exception as exc:
            return {
                "success": False,
                "message": f"生成随访建议失败: {str(exc)}",
                "suggestion": "",
            }

    def _build_followup_prompt(self, history: List[Dict]) -> str:
        prompt = """请根据以下患者的检查历史，制定个性化的随访计划。

检查历史:
"""
        for idx, exam in enumerate(history, 1):
            prompt += f"""
检查 #{idx}:
- 日期: {exam.get('exam_date', '未知')}
- 息肉数量: {exam.get('polyp_count', 0)}
- 风险等级: {exam.get('risk_level', 'unknown')}
- 病理类型: {exam.get('pathology_type', '未知')}
"""

        prompt += """

请提供:
1. 下次建议检查时间
2. 检查项目建议
3. 生活方式指导
4. 需要关注的风险因素
"""
        return prompt


llm_service = LLMService()
