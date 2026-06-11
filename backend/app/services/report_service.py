"""
PDF report generation service.
"""

from __future__ import annotations

from datetime import datetime
from html import escape
from io import BytesIO
from pathlib import Path
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.pdfmetrics import registerFont
from reportlab.platypus import Image as PlatypusImage
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


registerFont(UnicodeCIDFont("STSong-Light"))


TEXT = {
    "title": "\u667a\u80fd\u606f\u8089\u8bca\u7597\u8f85\u52a9\u5e73\u53f0\u786e\u8ba4\u7248\u62a5\u544a",
    "subtitle": "\u672c\u62a5\u544a\u57fa\u4e8e\u533b\u751f\u5ba1\u6838\u4e0e\u786e\u8ba4\u540e\u7684\u5185\u5bb9\u751f\u6210\uff0c\u4ec5\u4f9b\u4e34\u5e8a\u53c2\u8003\u3002",
    "section_images": "\u68c0\u67e5\u56fe\u50cf\u4e0e\u5206\u5272\u7ed3\u679c",
    "section_summary": "\u6838\u5fc3\u7ed3\u8bba",
    "section_clinical_report": "\u533b\u751f\u786e\u8ba4\u7248\u533b\u5b66\u62a5\u544a",
    "section_treatment": "\u5904\u7f6e\u5efa\u8bae",
    "section_followup": "\u968f\u8bbf\u5efa\u8bae",
    "section_history": "\u5386\u53f2\u5bf9\u6bd4\u7ed3\u8bba",
    "section_progression": "\u8fdb\u5c55\u8bc4\u4f30",
    "risk_label": "\u98ce\u9669\u7b49\u7ea7",
    "pathology_label": "\u75c5\u7406\u503e\u5411",
    "unknown": "\u672a\u586b\u5199",
    "unrecorded": "\u672a\u8bb0\u5f55",
    "patient_name": "\u60a3\u8005\u59d3\u540d",
    "gender": "\u6027\u522b",
    "age": "\u5e74\u9f84",
    "phone": "\u8054\u7cfb\u7535\u8bdd",
    "exam_type": "\u68c0\u67e5\u7c7b\u578b",
    "model": "\u5206\u6790\u6a21\u578b",
    "exam_time": "\u68c0\u67e5\u65f6\u95f4",
    "confirmed_time": "\u786e\u8ba4\u65f6\u95f4",
    "doctor_name": "\u533b\u5e08\u59d3\u540d",
    "exam_id": "\u68c0\u67e5\u7f16\u53f7",
    "pending_image": "\u672c\u6b21\u68c0\u67e5\u5f85\u5206\u5272\u56fe",
    "result_image": "\u5206\u5272\u7ed3\u679c\u56fe",
    "no_image": "\u6682\u65e0\u56fe\u50cf",
    "male": "\u7537",
    "female": "\u5973",
    "colonoscopy": "\u7ed3\u80a0\u955c",
    "gastroscopy": "\u80c3\u955c",
    "enteroscopy": "\u5c0f\u80a0\u955c",
    "sigmoidoscopy": "\u4e59\u72b6\u7ed3\u80a0\u955c",
    "low_risk": "\u4f4e\u98ce\u9669",
    "medium_risk": "\u4e2d\u98ce\u9669",
    "high_risk": "\u9ad8\u98ce\u9669",
}


class ReportService:
    def __init__(self):
        styles = getSampleStyleSheet()
        self.title_style = ParagraphStyle(
            "ReportTitle",
            parent=styles["Title"],
            fontName="STSong-Light",
            fontSize=18,
            leading=24,
            alignment=TA_LEFT,
            textColor=colors.HexColor("#1F4E79"),
            spaceAfter=10,
        )
        self.section_style = ParagraphStyle(
            "ReportSection",
            parent=styles["Heading2"],
            fontName="STSong-Light",
            fontSize=12,
            leading=18,
            textColor=colors.HexColor("#1F4E79"),
            spaceBefore=10,
            spaceAfter=6,
        )
        self.body_style = ParagraphStyle(
            "ReportBody",
            parent=styles["BodyText"],
            fontName="STSong-Light",
            fontSize=10.5,
            leading=16,
            textColor=colors.black,
            spaceAfter=5,
        )
        self.image_caption_style = ParagraphStyle(
            "ReportImageCaption",
            parent=self.body_style,
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#1F4E79"),
            spaceAfter=4,
        )

    def build_confirmed_report_pdf(
        self,
        *,
        patient_name: str,
        patient_gender: Optional[str],
        patient_age: Optional[int],
        patient_phone: Optional[str],
        examination_id: str,
        exam_date: Optional[datetime],
        exam_type: Optional[str],
        model_label: str,
        confirmed_report: dict,
        reviewed_at: Optional[datetime],
        doctor_name: str = "\u5f20\u533b\u5e08",
        source_image_path: Optional[str] = None,
        segmentation_image_path: Optional[str] = None,
    ) -> bytes:
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=18 * mm,
            rightMargin=18 * mm,
            topMargin=16 * mm,
            bottomMargin=16 * mm,
        )

        story = [
            Paragraph(TEXT["title"], self.title_style),
            Paragraph(TEXT["subtitle"], self.body_style),
            Spacer(1, 4),
            self._build_meta_table(
                patient_name=patient_name,
                patient_gender=patient_gender,
                patient_age=patient_age,
                patient_phone=patient_phone,
                examination_id=examination_id,
                exam_date=exam_date,
                exam_type=exam_type,
                model_label=model_label,
                reviewed_at=reviewed_at,
                doctor_name=doctor_name,
            ),
            Spacer(1, 10),
        ]

        image_section = self._build_image_section(
            source_image_path=source_image_path,
            segmentation_image_path=segmentation_image_path,
        )
        if image_section is not None:
            story.extend(
                [
                    Paragraph(TEXT["section_images"], self.section_style),
                    image_section,
                    Spacer(1, 10),
                ]
            )

        risk_level = self._translate_risk_level(confirmed_report.get("risk_level")) or TEXT["unknown"]
        pathology_type = confirmed_report.get("pathology_type") or TEXT["unknown"]
        story.extend(
            [
                Paragraph(TEXT["section_summary"], self.section_style),
                Paragraph(f'{TEXT["risk_label"]}\uff1a{escape(str(risk_level))}', self.body_style),
                Paragraph(f'{TEXT["pathology_label"]}\uff1a{escape(str(pathology_type))}', self.body_style),
                Paragraph(TEXT["section_clinical_report"], self.section_style),
                self._paragraph_from_text(confirmed_report.get("clinical_report") or TEXT["unknown"]),
                Paragraph(TEXT["section_treatment"], self.section_style),
                self._paragraph_from_text(confirmed_report.get("treatment_recommendation") or TEXT["unknown"]),
                Paragraph(TEXT["section_followup"], self.section_style),
                self._paragraph_from_text(confirmed_report.get("followup_plan") or TEXT["unknown"]),
            ]
        )

        historical_comparison = (confirmed_report.get("historical_comparison") or "").strip()
        if historical_comparison:
            story.extend(
                [
                    Paragraph(TEXT["section_history"], self.section_style),
                    self._paragraph_from_text(historical_comparison),
                ]
            )

        progression_assessment = (confirmed_report.get("progression_assessment") or "").strip()
        if progression_assessment:
            story.extend(
                [
                    Paragraph(TEXT["section_progression"], self.section_style),
                    self._paragraph_from_text(progression_assessment),
                ]
            )

        doc.build(story)
        return buffer.getvalue()

    def _build_meta_table(
        self,
        *,
        patient_name: str,
        patient_gender: Optional[str],
        patient_age: Optional[int],
        patient_phone: Optional[str],
        examination_id: str,
        exam_date: Optional[datetime],
        exam_type: Optional[str],
        model_label: str,
        reviewed_at: Optional[datetime],
        doctor_name: str,
    ) -> Table:
        gender_text = self._translate_gender(patient_gender)
        exam_type_text = self._translate_exam_type(exam_type)
        age_text = f"{patient_age} \u5c81" if patient_age is not None else TEXT["unknown"]

        rows = [
            [TEXT["patient_name"], patient_name or TEXT["unknown"], TEXT["gender"], gender_text],
            [TEXT["age"], age_text, TEXT["phone"], patient_phone or TEXT["unknown"]],
            [TEXT["exam_type"], exam_type_text, TEXT["model"], model_label or TEXT["unrecorded"]],
            [TEXT["exam_time"], self._format_datetime(exam_date), TEXT["confirmed_time"], self._format_datetime(reviewed_at)],
            [TEXT["doctor_name"], doctor_name or TEXT["unknown"], TEXT["exam_id"], examination_id or TEXT["unknown"]],
        ]
        table = Table(rows, colWidths=[26 * mm, 56 * mm, 26 * mm, 56 * mm])
        table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), "STSong-Light"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("BACKGROUND", (0, 0), (-1, -1), colors.whitesmoke),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D9D9D9")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EAF2FA")),
                    ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#EAF2FA")),
                ]
            )
        )
        return table

    def _build_image_section(
        self,
        *,
        source_image_path: Optional[str],
        segmentation_image_path: Optional[str],
    ) -> Optional[Table]:
        if not source_image_path and not segmentation_image_path:
            return None

        left_cell = self._build_image_cell(TEXT["pending_image"], source_image_path)
        right_cell = self._build_image_cell(TEXT["result_image"], segmentation_image_path)
        table = Table([[left_cell, right_cell]], colWidths=[82 * mm, 82 * mm])
        table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#D9D9D9")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D9D9D9")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ]
            )
        )
        return table

    def _build_image_cell(self, title: str, image_path: Optional[str]) -> list:
        content = [Paragraph(title, self.image_caption_style)]
        report_image = self._build_report_image(image_path)
        if report_image is None:
            content.append(Paragraph(TEXT["no_image"], self.body_style))
        else:
            content.append(report_image)
        return content

    def _build_report_image(self, image_path: Optional[str]) -> Optional[PlatypusImage]:
        if not image_path:
            return None

        path = Path(image_path)
        if not path.exists() or not path.is_file():
            return None

        width_pt, height_pt = self._get_scaled_image_size(path, max_width=74 * mm, max_height=74 * mm)
        return PlatypusImage(str(path), width=width_pt, height=height_pt)

    def _get_scaled_image_size(self, image_path: Path, *, max_width: float, max_height: float) -> tuple[float, float]:
        from PIL import Image as PILImage

        with PILImage.open(image_path) as img:
            original_width, original_height = img.size

        if original_width <= 0 or original_height <= 0:
            return max_width, max_height

        scale = min(max_width / original_width, max_height / original_height)
        return original_width * scale, original_height * scale

    def _paragraph_from_text(self, text: str) -> Paragraph:
        safe_text = escape(text).replace("\n", "<br/>")
        return Paragraph(safe_text, self.body_style)

    def _format_datetime(self, value: Optional[datetime]) -> str:
        if not value:
            return TEXT["unknown"]
        return value.strftime("%Y-%m-%d %H:%M")

    def _translate_gender(self, value: Optional[str]) -> str:
        if not value:
            return TEXT["unknown"]

        normalized = str(value).strip().lower()
        mapping = {
            "m": TEXT["male"],
            "male": TEXT["male"],
            "man": TEXT["male"],
            "\u7537": TEXT["male"],
            "f": TEXT["female"],
            "female": TEXT["female"],
            "woman": TEXT["female"],
            "\u5973": TEXT["female"],
        }
        return mapping.get(normalized, str(value))

    def _translate_exam_type(self, value: Optional[str]) -> str:
        if not value:
            return TEXT["unknown"]

        normalized = str(value).strip().lower()
        mapping = {
            "colonoscopy": TEXT["colonoscopy"],
            "gastroscopy": TEXT["gastroscopy"],
            "enteroscopy": TEXT["enteroscopy"],
            "sigmoidoscopy": TEXT["sigmoidoscopy"],
            "\u7ed3\u80a0\u955c": TEXT["colonoscopy"],
            "\u80c3\u955c": TEXT["gastroscopy"],
        }
        return mapping.get(normalized, str(value))

    def _translate_risk_level(self, value: Optional[str]) -> str:
        if not value:
            return TEXT["unknown"]

        normalized = str(value).strip().lower()
        mapping = {
            "low": TEXT["low_risk"],
            "medium": TEXT["medium_risk"],
            "high": TEXT["high_risk"],
            "\u4f4e": TEXT["low_risk"],
            "\u4e2d": TEXT["medium_risk"],
            "\u9ad8": TEXT["high_risk"],
            "\u4f4e\u98ce\u9669": TEXT["low_risk"],
            "\u4e2d\u98ce\u9669": TEXT["medium_risk"],
            "\u9ad8\u98ce\u9669": TEXT["high_risk"],
        }
        return mapping.get(normalized, str(value))


report_service = ReportService()
