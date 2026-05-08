import os
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = str(Path(__file__).parent.parent)
sys.path.append(project_root)

from src.performance.cache_optimizer import get_cache_optimizer
import time

def test_redis_caching():
    print("Testing Redis Caching...")
    cache = get_cache_optimizer()
    
    if not cache.redis_client:
        print("Redis client not available. Skipping test.")
        return

    test_key = "test_query_123"
    test_data = [{"id": 1, "text": "Result 1"}, {"id": 2, "text": "Result 2"}]
    
    # 1. 保存
    print(f"Setting cache for '{test_key}'...")
    cache.set(test_key, test_data, namespace="test")
    
    # 2. 取得
    print(f"Getting cache for '{test_key}'...")
    cached_data = cache.get(test_key, namespace="test")
    
    if cached_data == test_data:
        print("✅ Cache hit successful and data matches!")
    else:
        print(f"❌ Cache mismatch: Expected {test_data}, got {cached_data}")

    # 3. 削除
    print(f"Deleting cache for '{test_key}'...")
    cache.delete(test_key, namespace="test")
    
    # 4. 削除確認
    if cache.get(test_key, namespace="test") is None:
        print("✅ Cache deletion successful!")
    else:
        print("❌ Cache deletion failed.")

if __name__ == "__main__":
    test_redis_caching()
