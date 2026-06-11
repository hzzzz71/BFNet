"""
API测试脚本
测试核心功能是否正常工作
"""

import requests
import json
import sys

BASE_URL = "http://localhost:8000"


def test_health():
    """测试健康检查接口"""
    print("🏥 测试健康检查接口...")
    try:
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 健康检查通过: {data}")
            return True
        else:
            print(f"❌ 健康检查失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        return False


def test_create_patient():
    """测试创建患者"""
    print("\n👤 测试创建患者...")
    patient_data = {
        "name": "测试患者",
        "gender": "M",
        "age": 45,
        "phone": "13800138000",
        "medical_history": "无特殊病史"
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/patients",
            json=patient_data,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 201:
            data = response.json()
            print(f"✅ 创建患者成功: ID={data['id']}")
            return data['id']
        else:
            print(f"❌ 创建患者失败: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return None


def test_list_patients():
    """测试获取患者列表"""
    print("\n📋 测试获取患者列表...")
    try:
        response = requests.get(f"{BASE_URL}/api/v1/patients")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 获取患者列表成功: 共 {len(data)} 位患者")
            return True
        else:
            print(f"❌ 获取患者列表失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return False


def test_model_status():
    """测试模型状态"""
    print("\n🤖 测试模型状态...")
    try:
        response = requests.get(f"{BASE_URL}/")
        if response.status_code == 200:
            data = response.json()
            if data.get("model_loaded"):
                print("✅ BFNet模型已加载")
            else:
                print("⚠️  BFNet模型未加载 (不影响其他功能)")
            return True
        else:
            print(f"❌ 状态检查失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return False


def run_all_tests():
    """运行所有测试"""
    print("=" * 50)
    print("智能息肉诊疗辅助平台 - API测试")
    print("=" * 50)
    
    all_passed = True
    
    # 测试1: 健康检查
    all_passed &= test_health()
    
    # 测试2: 模型状态
    all_passed &= test_model_status()
    
    # 测试3: 创建患者
    patient_id = test_create_patient()
    all_passed &= (patient_id is not None)
    
    # 测试4: 获取患者列表
    all_passed &= test_list_patients()
    
    print("\n" + "=" * 50)
    if all_passed:
        print("✅ 所有测试通过！系统运行正常")
        print("\n下一步:")
        print("1. 在浏览器中打开 http://localhost:8000/docs 查看API文档")
        print("2. 使用前端界面上传图像进行息肉分割测试")
        print("3. 配置OPENAI_API_KEY以启用LLM分析功能")
    else:
        print("❌ 部分测试失败，请检查错误信息")
        print("\n常见问题:")
        print("1. 确保Docker服务已启动")
        print("2. 检查后端容器是否正常运行: docker-compose ps")
        print("3. 查看后端日志: docker-compose logs backend")
    print("=" * 50)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
