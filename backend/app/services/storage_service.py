"""
文件存储服务
管理文件上传、下载、删除等操作
"""

import os
import uuid
import numpy as np
from pathlib import Path
from typing import Optional
from fastapi import UploadFile
from minio import Minio
from minio.error import S3Error

from app.core.config import settings


class StorageService:
    """文件存储服务类"""
    
    def __init__(self):
        self.use_minio = settings.MINIO_ENDPOINT and settings.MINIO_ACCESS_KEY
        self.local_storage_path = Path("data/uploads")
        self.local_storage_path.mkdir(parents=True, exist_ok=True)
        
        if self.use_minio:
            self.minio_client = Minio(
                settings.MINIO_ENDPOINT,
                access_key=settings.MINIO_ACCESS_KEY,
                secret_key=settings.MINIO_SECRET_KEY,
                secure=settings.MINIO_SECURE
            )
            self._ensure_bucket_exists()
    
    def _ensure_bucket_exists(self):
        """确保MinIO存储桶存在"""
        try:
            if not self.minio_client.bucket_exists(settings.MINIO_BUCKET):
                self.minio_client.make_bucket(settings.MINIO_BUCKET)
                print(f"MinIO存储桶创建成功: {settings.MINIO_BUCKET}")
        except Exception as e:
            print(f"MinIO存储桶检查失败: {e}")
            self.use_minio = False
    
    async def save_upload_file(self, file: UploadFile, patient_id: uuid.UUID) -> str:
        """
        保存上传的文件
        
        Args:
            file: FastAPI UploadFile对象
            patient_id: 患者ID
            
        Returns:
            文件存储路径
        """
        # 生成文件名
        file_ext = Path(file.filename).suffix
        new_filename = f"{uuid.uuid4()}{file_ext}"
        
        # 构建存储路径: patient_id/年/月/文件名
        current_date = Path(str(uuid.uuid4())) / str(patient_id) / new_filename
        
        if self.use_minio:
            # 上传到MinIO
            return await self._upload_to_minio(file, current_date)
        else:
            # 保存到本地文件系统
            return await self._save_to_local(file, current_date)
    
    async def _upload_to_minio(self, file: UploadFile, object_name: Path) -> str:
        """上传到MinIO"""
        try:
            # 读取文件内容
            contents = await file.read()
            
            # 上传到MinIO
            self.minio_client.put_object(
                settings.MINIO_BUCKET,
                str(object_name),
                contents,
                length=len(contents),
                content_type=file.content_type
            )
            
            # 返回对象URL
            return f"minio://{settings.MINIO_BUCKET}/{object_name}"
            
        except S3Error as e:
            raise Exception(f"MinIO上传失败: {e}")
        finally:
            await file.seek(0)  # 重置文件指针
    
    async def _save_to_local(self, file: UploadFile, relative_path: Path) -> str:
        """保存到本地文件系统"""
        # 构建完整路径
        full_path = self.local_storage_path / relative_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            # 保存文件
            contents = await file.read()
            with open(full_path, "wb") as f:
                f.write(contents)
            
            # 返回相对路径
            return str(relative_path)
            
        except Exception as e:
            raise Exception(f"本地文件保存失败: {e}")
        finally:
            await file.seek(0)
    
    async def save_segmentation_result(self, result_image, patient_id: uuid.UUID, original_filename: str) -> str:
        """
        保存分割结果图像
        
        Args:
            result_image: 分割结果图像 (numpy array或PIL Image)
            patient_id: 患者ID
            original_filename: 原始文件名
            
        Returns:
            文件存储路径
        """
        import cv2
        from PIL import Image
        
        # 生成文件名
        file_ext = Path(original_filename).suffix
        result_filename = f"result_{uuid.uuid4()}{file_ext}"
        
        # 构建存储路径
        current_date = Path(str(uuid.uuid4())) / str(patient_id) / result_filename
        
        if self.use_minio:
            # 上传到MinIO
            return self._save_image_to_minio(result_image, current_date)
        else:
            # 保存到本地
            return self._save_image_to_local(result_image, current_date)
    
    def _save_image_to_local(self, image, relative_path: Path) -> str:
        """保存图像到本地"""
        import cv2
        from PIL import Image
        
        full_path = self.local_storage_path / relative_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        
        if isinstance(image, np.ndarray):
            # OpenCV图像
            cv2.imwrite(str(full_path), cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
        else:
            # PIL Image
            image.save(full_path)
        
        return str(relative_path)
    
    def _save_image_to_minio(self, image, object_name: Path) -> str:
        """保存图像到MinIO"""
        import cv2
        from PIL import Image
        import io
        
        # 转换图像为字节
        if isinstance(image, np.ndarray):
            # OpenCV图像
            is_success, buffer = cv2.imencode(".png", cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
            if not is_success:
                raise Exception("图像编码失败")
            image_bytes = io.BytesIO(buffer)
        else:
            # PIL Image
            image_bytes = io.BytesIO()
            image.save(image_bytes, format='PNG')
            image_bytes.seek(0)
        
        # 上传到MinIO
        self.minio_client.put_object(
            settings.MINIO_BUCKET,
            str(object_name),
            image_bytes,
            length=image_bytes.getbuffer().nbytes,
            content_type="image/png"
        )
        
        return f"minio://{settings.MINIO_BUCKET}/{object_name}"
    
    def get_file_url(self, file_path: str) -> str:
        """
        获取文件访问URL
        
        Args:
            file_path: 文件存储路径
            
        Returns:
            可访问的URL
        """
        if file_path.startswith("minio://"):
            # MinIO对象
            object_name = file_path.replace(f"minio://{settings.MINIO_BUCKET}/", "")
            try:
                url = self.minio_client.presigned_get_object(
                    settings.MINIO_BUCKET,
                    object_name,
                    expires_seconds=3600  # 1小时有效期
                )
                return url
            except S3Error:
                return ""
        else:
            # 本地文件
            full_path = self.local_storage_path / file_path
            if full_path.exists():
                return f"/local-file/{file_path}"  # 需要配合前端路由
            else:
                return ""
    
    def delete_file(self, file_path: str) -> bool:
        """
        删除文件
        
        Args:
            file_path: 文件存储路径
            
        Returns:
            是否删除成功
        """
        try:
            if file_path.startswith("minio://"):
                # 删除MinIO对象
                object_name = file_path.replace(f"minio://{settings.MINIO_BUCKET}/", "")
                self.minio_client.remove_object(settings.MINIO_BUCKET, object_name)
            else:
                # 删除本地文件
                full_path = self.local_storage_path / file_path
                if full_path.exists():
                    full_path.unlink()
            
            return True
            
        except Exception as e:
            print(f"删除文件失败 {file_path}: {e}")
            return False


# 全局单例
storage_service = StorageService()
