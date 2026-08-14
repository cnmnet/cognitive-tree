#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, List, Tuple

from governance.config import Config

class VectorStore:
    """
    向量存储引擎 —— 基于 ChromaDB 的语义检索

    将晶体卡片向量化，支持语义相似度检索。
    首次运行时自动下载 sentence-transformers 模型（all-MiniLM-L6-v2）。
    检索失败时自动降级到 BM25（由调用方处理）。
    """

    def __init__(self, file_io: Any, model_name: str = "all-MiniLM-L6-v2"):
        self.files = file_io
        self.model_name = model_name
        self._model = None
        self._collection = None
        self._initialized = False

        # 向量数据库存储路径
        self._db_path = Config.DATA_ROOT / "model_cache" / "chroma_db"
        self._init_vector_store()

    def _init_vector_store(self) -> None:
        """初始化向量存储（延迟加载模型）"""
        try:
            import chromadb
            from chromadb.config import Settings

            # 创建存储目录
            self._db_path.mkdir(parents=True, exist_ok=True)

            # 初始化 ChromaDB 客户端（持久化）
            self._client = chromadb.PersistentClient(
                path=str(self._db_path),
                settings=Settings(anonymized_telemetry=False)
            )

            # 获取或创建 collection
            self._collection = self._client.get_or_create_collection(
                name="crystals",
                metadata={"hnsw:space": "cosine"}
            )

            self._initialized = True
            print(f"[OK] VectorStore 初始化成功，已有 {self._collection.count()} 条向量")
        except ImportError:
            print("[WARN] chromadb 未安装，向量检索不可用，将使用 BM25 降级")
            self._initialized = False
        except Exception as e:
            print(f"[WARN] VectorStore 初始化失败: {e}，将使用 BM25 降级")
            self._initialized = False

    def _get_model(self):
        """延迟加载 sentence-transformers 模型"""
        if self._model is not None:
            return self._model

        if not self._initialized:
            return None

        try:
            from sentence_transformers import SentenceTransformer
            # 设置 HuggingFace 镜像
            import os
            os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
            self._model = SentenceTransformer(self.model_name)
            print(f"✅ 向量模型 {self.model_name} 加载成功")
            return self._model
        except ImportError:
            print("⚠️ sentence_transformers 未安装")
            return None
        except Exception as e:
            print(f"⚠️ 模型加载失败: {e}")
            return None

    def add_crystals(self, crystals: List) -> int:
        """
        将晶体批量添加到向量库

        Returns:
            成功添加的数量
        """
        if not self._initialized or not crystals:
            return 0

        model = self._get_model()
        if model is None:
            return 0

        try:
            # 准备数据
            ids = [c.id for c in crystals]
            documents = [c.content for c in crystals]
            # 附加元数据
            metadatas = [{"layer": c.layer.value if hasattr(c.layer, 'value') else str(c.layer)} for c in crystals]

            # 生成向量
            embeddings = model.encode(documents, show_progress_bar=False).tolist()

            # 分批插入（避免一次性过大）
            batch_size = 50
            for i in range(0, len(ids), batch_size):
                batch_end = min(i + batch_size, len(ids))
                self._collection.add(
                    ids=ids[i:batch_end],
                    documents=documents[i:batch_end],
                    embeddings=embeddings[i:batch_end],
                    metadatas=metadatas[i:batch_end]
                )

            print(f"✅ 成功向量化 {len(ids)} 条晶体")
            return len(ids)

        except Exception as e:
            print(f"[WARN] 向量化失败: {e}")
            return 0

    def query(self, query_text: str, top_k: int = 5) -> List[Tuple[str, float]]:
        """
        语义检索最相似的晶体

        Returns:
            List[(crystal_id, similarity_score), ...]
        """
        if not self._initialized:
            return []

        model = self._get_model()
        if model is None:
            return []

        try:
            # 生成查询向量
            query_embedding = model.encode(query_text, show_progress_bar=False).tolist()

            # 检索
            results = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                include=["documents", "metadatas", "distances"]
            )

            # 解析结果
            if results and results.get('ids') and len(results['ids']) > 0:
                ids = results['ids'][0]
                distances = results['distances'][0] if results.get('distances') else []
                # 距离转相似度（cosine距离 → 相似度）
                similarities = [1 - d for d in distances] if distances else []
                return list(zip(ids, similarities))

            return []

        except Exception as e:
            print(f"⚠️ 向量检索失败: {e}")
            return []

    def delete_crystal(self, crystal_id: str) -> bool:
        """从向量库删除单个晶体"""
        if not self._initialized:
            return False

        try:
            self._collection.delete(ids=[crystal_id])
            return True
        except Exception as e:
            print(f"⚠️ 删除向量失败: {e}")
            return False

    def count(self) -> int:
        """获取向量库中的晶体数量"""
        if not self._initialized:
            return 0
        try:
            return self._collection.count()
        except:
            return 0

    def reset(self) -> bool:
        """重置向量库（删除所有数据）"""
        if not self._initialized:
            return False
        try:
            self._client.delete_collection("crystals")
            self._collection = self._client.create_collection("crystals")
            return True
        except Exception as e:
            print(f"⚠️ 重置向量库失败: {e}")
            return False

    def is_available(self) -> bool:
        """检查向量检索是否可用"""
        return self._initialized and self._get_model() is not None

