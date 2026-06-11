"""
图像处理工具类
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Union, Tuple


class ImageProcessor:
    """图像处理工具类"""
    
    def __init__(self):
        self.supported_formats = {'.jpg', '.jpeg', '.png', '.tiff', '.bmp', '.tif'}
    
    async def read_image(self, file_path: Union[str, Path]) -> np.ndarray:
        """
        读取图像文件
        
        Args:
            file_path: 图像文件路径
            
        Returns:
            RGB格式的numpy数组
        """
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"图像文件不存在: {file_path}")
        
        if path.suffix.lower() not in self.supported_formats:
            raise ValueError(f"不支持的图像格式: {path.suffix}")
        
        # 读取图像
        image = cv2.imread(str(file_path))
        if image is None:
            raise Exception(f"无法读取图像: {file_path}")
        
        # 转换为RGB
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        return image_rgb
    
    def resize_image(self, image: np.ndarray, size: Tuple[int, int]) -> np.ndarray:
        """
        调整图像大小
        
        Args:
            image: 输入图像
            size: (width, height)
            
        Returns:
            调整大小后的图像
        """
        return cv2.resize(image, size)
    
    def normalize_image(self, image: np.ndarray) -> np.ndarray:
        """
        归一化图像到[0, 1]范围
        
        Args:
            image: 输入图像 (0-255)
            
        Returns:
            归一化后的图像 (0.0-1.0)
        """
        return image.astype(np.float32) / 255.0
    
    def denormalize_image(self, image: np.ndarray) -> np.ndarray:
        """
        反归一化图像到[0, 255]范围
        
        Args:
            image: 输入图像 (0.0-1.0)
            
        Returns:
            反归一化后的图像 (0-255)
        """
        return (image * 255).astype(np.uint8)
    
    def generate_thumbnail(self, image: np.ndarray, max_size: int = 256) -> np.ndarray:
        """
        生成缩略图
        
        Args:
            image: 输入图像
            max_size: 最大边长
            
        Returns:
            缩略图
        """
        h, w = image.shape[:2]
        
        if h > w:
            new_h, new_w = max_size, int(w * max_size / h)
        else:
            new_h, new_w = int(h * max_size / w), max_size
        
        return self.resize_image(image, (new_w, new_h))
    
    def calculate_image_hash(self, image: np.ndarray) -> str:
        """
        计算图像哈希值 (用于去重)
        
        Args:
            image: 输入图像
            
        Returns:
            哈希字符串
        """
        # 缩小图像以加快计算
        small_image = self.resize_image(image, (64, 64))
        
        # 转换为灰度图
        gray = cv2.cvtColor(small_image, cv2.COLOR_RGB2GRAY)
        
        # 计算平均值
        avg = gray.mean()
        
        # 生成哈希
        hash_bits = gray > avg
        hash_str = ''.join('1' if bit else '0' for bit in hash_bits.flatten())
        
        return hash_str
