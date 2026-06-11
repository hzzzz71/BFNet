"""
BFNet模型推理服务
加载模型并提供预测接口
"""

import os
import sys
import numpy as np
from PIL import Image
import cv2
from typing import Tuple, List, Dict, Optional, Any
from pathlib import Path

try:
    import torch
    import torch.nn.functional as F
except ImportError:
    torch = None
    F = None
from app.core.config import settings


def load_checkpoint(checkpoint_path: Path, map_location: str):
    try:
        return torch.load(str(checkpoint_path), map_location=map_location, weights_only=True)
    except TypeError:
        return torch.load(str(checkpoint_path), map_location=map_location)


class ModelService:
    """BFNet息肉分割模型服务"""
    
    def __init__(self):
        self.model = None
        self.device = settings.MODEL_DEVICE if torch and torch.cuda.is_available() else "cpu"
        self.image_size = settings.MODEL_IMAGE_SIZE
        
    def load_model(self, model_path: str = None):
        """加载BFNet模型"""
        if torch is None:
            raise RuntimeError("未安装torch，无法加载BFNet模型")

        if model_path is None:
            model_path = settings.MODEL_PATH

        model_path_obj = Path(model_path).resolve()
        if not model_path_obj.exists():
            raise FileNotFoundError(f"模型文件不存在: {model_path}")

        project_root = Path(__file__).resolve().parents[3]
        candidate_roots = [
            model_path_obj.parent,
            model_path_obj.parent.parent,
            project_root / "BFNet",
        ]

        bfnet_root = None
        for candidate in candidate_roots:
            if (candidate / "model" / "BFNet.py").exists():
                bfnet_root = candidate
                break

        if bfnet_root is None:
            raise RuntimeError(f"未找到BFNet代码目录: {model_path_obj.parent.parent}")

        if model_path_obj.name.lower().startswith("pvt"):
            candidate_weight = bfnet_root / "model" / "BFNet.pth"
            if candidate_weight.exists():
                model_path_obj = candidate_weight

        if str(bfnet_root) not in sys.path:
            sys.path.append(str(bfnet_root))

        pvt_path = Path(settings.MODEL_PVT_PATH).resolve()
        if pvt_path.exists():
            os.environ["BFNET_PVT_PATH"] = str(pvt_path)

        try:
            from model.BFNet import BFNet
        except ImportError as exc:
            raise RuntimeError(f"未找到BFNet代码目录: {bfnet_root}") from exc
        
        print("正在加载BFNet模型...")
        print(f"   模型路径: {model_path_obj}")
        print(f"   设备: {self.device}")
        
        # 初始化模型
        self.model = BFNet(
            channel=32,
            kernel_size=3,
            reduction=4,
            bias=False,
            act=torch.nn.PReLU(),
            n_resblocks=2,
            iteration=3
        )
        
        # 加载权重
        checkpoint = load_checkpoint(model_path_obj, self.device)
        if isinstance(checkpoint, dict) and "state_dict" in checkpoint:
            checkpoint = checkpoint["state_dict"]
        self.model.load_state_dict(checkpoint)
        self.model.to(self.device)
        self.model.eval()
        
        print("BFNet模型加载成功")
        
    def unload_model(self):
        """卸载模型释放内存"""
        if self.model is not None:
            del self.model
            self.model = None
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            print("模型已卸载")
    
    def preprocess_image(self, image: np.ndarray) -> Any:
        """预处理图像"""
        # 转换为RGB
        if len(image.shape) == 2:
            image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
        elif image.shape[2] == 4:
            image = cv2.cvtColor(image, cv2.COLOR_RGBA2RGB)
        
        # 调整大小
        image = cv2.resize(image, (self.image_size, self.image_size))
        
        # 归一化
        image = image.astype(np.float32) / 255.0
        
        # 转换为tensor并调整维度
        image_tensor = torch.from_numpy(image).permute(2, 0, 1)  # HWC -> CHW
        
        return image_tensor.unsqueeze(0)  # 添加batch维度
    
    def generate_depth_map(self, image: np.ndarray) -> np.ndarray:
        """生成深度图 (模拟或从文件中读取)"""
        # TODO: 实际项目中应该从depth文件中读取
        # 这里使用简化版本: 基于图像梯度的模拟深度
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        grad_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        grad_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        depth = np.sqrt(grad_x**2 + grad_y**2)
        depth = (depth - depth.min()) / (depth.max() - depth.min() + 1e-8)
        depth = (depth * 255).astype(np.uint8)
        return cv2.cvtColor(depth, cv2.COLOR_GRAY2RGB)
    
    def predict(self, image: np.ndarray) -> Dict:
        """
        执行息肉分割预测
        
        Args:
            image: 输入图像 (RGB格式)
            
        Returns:
            分割结果字典
        """
        if self.model is None:
            raise RuntimeError("模型未加载，请先调用load_model()")
        
        try:
            # 预处理
            image_tensor = self.preprocess_image(image).to(self.device)
            
            # 生成深度图并预处理
            depth_image = self.generate_depth_map(image)
            depth_tensor = self.preprocess_image(depth_image).to(self.device)
            
            # 拼接输入 (双模态)
            input_tensor = torch.cat([image_tensor, depth_tensor], dim=0)
            
            # 模型推理
            with torch.no_grad():
                stage_preds, final_pred = self.model(input_tensor)
            
            # 后处理
            final_pred = torch.sigmoid(final_pred)
            final_pred = F.interpolate(
                final_pred, 
                size=image.shape[:2], 
                mode='bilinear', 
                align_corners=False
            )
            
            pred_mask = final_pred.squeeze().cpu().numpy()
            pred_mask = (pred_mask > 0.5).astype(np.uint8)  # 二值化
            
            # 提取息肉信息
            polyp_info = self.extract_polyp_info(pred_mask, image.shape[:2])
            
            return {
                "success": True,
                "mask": pred_mask,
                "polyp_count": len(polyp_info),
                "polyps": polyp_info,
                "message": "分割成功"
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"分割失败: {str(e)}"
            }
    
    def extract_polyp_info(self, mask: np.ndarray, original_shape: Tuple[int, int]) -> List[Dict]:
        """从掩码中提取息肉信息"""
        # 查找轮廓
        contours, _ = cv2.findContours(
            mask, 
            cv2.RETR_EXTERNAL, 
            cv2.CHAIN_APPROX_SIMPLE
        )
        
        polyps = []
        for idx, contour in enumerate(contours):
            # 计算边界框
            x, y, w, h = cv2.boundingRect(contour)
            
            # 计算面积和周长
            area = cv2.contourArea(contour)
            perimeter = cv2.arcLength(contour, True)
            
            # 估算直径 (假设为圆形)
            diameter = np.sqrt(4 * area / np.pi)
            
            # 计算边界清晰度 (基于轮廓平滑度)
            if perimeter > 0:
                boundary_score = min(1.0, 4 * np.pi * area / (perimeter ** 2))
            else:
                boundary_score = 0.0
            
            # 形态分类 (基于宽高比)
            aspect_ratio = w / h if h > 0 else 0
            if aspect_ratio > 2.0:
                shape_type = "pedunculated"  # 有蒂
            elif aspect_ratio > 0.5:
                shape_type = "sessile"  # 无蒂
            else:
                shape_type = "flat"  # 扁平
            
            polyps.append({
                "number": idx + 1,
                "bbox": {
                    "x": int(x),
                    "y": int(y),
                    "width": int(w),
                    "height": int(h)
                },
                "area": float(area),
                "diameter_mm": float(diameter * 0.1),  # 假设像素到mm的转换
                "boundary_score": float(boundary_score),
                "shape_type": shape_type,
                "confidence": 0.95  # 模型置信度
            })
        
        return polyps
    
    def visualize_result(self, image: np.ndarray, mask: np.ndarray, polyps: List[Dict]) -> np.ndarray:
        """可视化分割结果"""
        # 复制原图
        vis_image = image.copy()
        
        # 绘制掩码轮廓
        contours, _ = cv2.findContours(
            mask.astype(np.uint8), 
            cv2.RETR_EXTERNAL, 
            cv2.CHAIN_APPROX_SIMPLE
        )
        
        # 绘制轮廓
        cv2.drawContours(vis_image, contours, -1, (0, 255, 0), 2)
        
        # 绘制息肉信息
        for polyp in polyps:
            bbox = polyp["bbox"]
            x, y = bbox["x"], bbox["y"]
            
            # 绘制边界框
            cv2.rectangle(
                vis_image,
                (x, y),
                (x + bbox["width"], y + bbox["height"]),
                (255, 0, 0),
                2
            )
            
            # 绘制标签
            label = f"#{polyp['number']} D:{polyp['diameter_mm']:.1f}mm"
            cv2.putText(
                vis_image,
                label,
                (x, y - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 0, 0),
                2
            )
        
        return vis_image


# 全局单例
model_service = ModelService()
