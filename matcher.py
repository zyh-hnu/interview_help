# semantic_matcher.py
import pandas as pd
from sentence_transformers import SentenceTransformer, util
import torch
import numpy as np
import os
import pickle
from typing import Dict, Optional, List
from functools import lru_cache

class SemanticQuestionMatcher:
    def __init__(self, knowledge_base_path: str, model_name: str ='shibing624/text2vec-base-chinese', 
                 cache_dir: str = './cache'):
        """
        初始化语义问题匹配器
        
        Args:
            knowledge_base_path: 知识库Excel文件路径
            model_name: 预训练模型名称，支持中文的推荐模型：
                       - 'paraphrase-multilingual-MiniLM-L12-v2' (多语言，轻量级)
                       - 'shibing624/text2vec-base-chinese' (中文专用)
                       - 'sentence-transformers/paraphrase-multilingual-mpnet-base-v2' (性能更好但更大)
            cache_dir: 缓存目录，用于存储预计算的向量
        """
        self.cache_dir = cache_dir
        self.model_name = model_name
        self.knowledge_base_path = knowledge_base_path
        
        # 创建缓存目录
        os.makedirs(cache_dir, exist_ok=True)
        
        try:
            # 1. 加载预训练的语义模型
            print(f"正在加载语义模型 '{model_name}'...")
            self.model = SentenceTransformer(model_name)
            print(f"语义模型加载成功！嵌入维度: {self.model.get_sentence_embedding_dimension()}")

            # 2. 加载知识库
            self._load_knowledge_base()
            
            # 3. 预计算或加载问题向量
            self._load_or_compute_embeddings()
            
        except FileNotFoundError:
            print(f"错误：找不到知识库文件 {knowledge_base_path}")
            raise
        except Exception as e:
            print(f"初始化时出错: {e}")
            raise

    def _load_knowledge_base(self):
        """加载知识库Excel文件"""
        df = pd.read_excel(self.knowledge_base_path)
        
        # 检查必要的列
        if 'question' not in df.columns or 'answer' not in df.columns:
            raise ValueError("Excel文件必须包含 'question' 和 'answer' 两列")
        
        # 清理数据
        df = df.dropna(subset=['question', 'answer'])
        
        self.questions = df['question'].astype(str).tolist()
        self.answers = df['answer'].astype(str).tolist()
        
        if len(self.questions) == 0:
            raise ValueError("知识库中没有有效的问题")
        
        print(f"知识库加载完成！共加载 {len(self.questions)} 个问题")

    def _get_cache_path(self):
        """获取缓存文件路径"""
        # 基于知识库文件和模型名称生成缓存文件名
        kb_name = os.path.splitext(os.path.basename(self.knowledge_base_path))[0]
        model_safe_name = self.model_name.replace('/', '_').replace('-', '_')
        return os.path.join(self.cache_dir, f"{kb_name}_{model_safe_name}_embeddings.pkl")

    def _load_or_compute_embeddings(self):
        """加载缓存的向量或重新计算"""
        cache_path = self._get_cache_path()
        
        # 尝试加载缓存
        if os.path.exists(cache_path):
            try:
                print("正在加载缓存的问题向量...")
                with open(cache_path, 'rb') as f:
                    cache_data = pickle.load(f)
                
                # 验证缓存数据的有效性
                if (cache_data.get('questions') == self.questions and 
                    cache_data.get('model_name') == self.model_name):
                    self.question_embeddings = cache_data['embeddings']
                    print("缓存向量加载成功！")
                    return
                else:
                    print("缓存数据已过期，重新计算向量...")
            except Exception as e:
                print(f"加载缓存失败: {e}，重新计算向量...")
        
        # 重新计算向量
        print("正在将知识库问题编码为语义向量...")
        self.question_embeddings = self.model.encode(
            self.questions, 
            convert_to_tensor=True, 
            show_progress_bar=True,
            batch_size=32  # 批处理以提高效率
        )
        
        # 保存到缓存
        try:
            cache_data = {
                'questions': self.questions,
                'model_name': self.model_name,
                'embeddings': self.question_embeddings
            }
            with open(cache_path, 'wb') as f:
                pickle.dump(cache_data, f)
            print(f"向量已缓存到: {cache_path}")
        except Exception as e:
            print(f"保存缓存失败: {e}")
        
        print(f"向量计算完成！维度: {self.question_embeddings.shape}")

    @lru_cache(maxsize=128) # 缓存最近128个不同的调用结果
    def match(self, text: str, threshold: float = 0.6, top_k: int = 1) -> Optional[Dict]:
        """
        匹配最相似的问题（基于语义）
        
        Args:
            text: 输入文本
            threshold: 相似度阈值，语义模型建议0.6-0.8
            top_k: 返回前k个最相似的结果
            
        Returns:
            匹配结果字典或None
        """
        if not text or not text.strip():
            return None
            
        try:
            # 1. 将输入文本编码为向量
            text_embedding = self.model.encode(text.strip(), convert_to_tensor=True)
            
            # 2. 计算余弦相似度
            similarities = util.cos_sim(text_embedding, self.question_embeddings)[0]
            
            # 3. 获取最相似的结果
            if top_k == 1:
                best_match_index = torch.argmax(similarities)
                max_similarity = similarities[best_match_index].item()
                
                matched_question = self.questions[best_match_index]
                
                print(f"识别文本: '{text}'")
                print(f"最匹配问题: '{matched_question}'")
                print(f"语义相似度: {max_similarity:.3f}")

                if max_similarity > threshold:
                    return {
                        'answer': self.answers[best_match_index],
                        'question': matched_question,
                        'similarity': float(max_similarity),
                        'index': int(best_match_index)
                    }
                else:
                    print(f"相似度 {max_similarity:.3f} 低于阈值 {threshold}，未找到匹配")
            else:
                # 返回top_k个结果
                top_indices = torch.topk(similarities, min(top_k, len(similarities)))[1]
                results = []
                
                for idx in top_indices:
                    similarity = similarities[idx].item()
                    if similarity > threshold:
                        results.append({
                            'answer': self.answers[idx],
                            'question': self.questions[idx],
                            'similarity': float(similarity),
                            'index': int(idx)
                        })
                
                if results:
                    print(f"识别文本: '{text}'")
                    print(f"找到 {len(results)} 个匹配结果")
                    return {'results': results}
                else:
                    print(f"没有找到相似度高于 {threshold} 的匹配")
        
        except Exception as e:
            print(f"匹配时出错: {e}")
        
        return None

    def batch_match(self, texts: List[str], threshold: float = 0.6) -> List[Optional[Dict]]:
        """
        批量匹配多个文本
        
        Args:
            texts: 文本列表
            threshold: 相似度阈值
            
        Returns:
            匹配结果列表
        """
        if not texts:
            return []
        
        try:
            # 批量编码输入文本
            text_embeddings = self.model.encode(texts, convert_to_tensor=True, show_progress_bar=True)
            
            # 计算所有文本与知识库的相似度
            similarities = util.cos_sim(text_embeddings, self.question_embeddings)
            
            results = []
            for i, text in enumerate(texts):
                best_match_index = torch.argmax(similarities[i])
                max_similarity = similarities[i][best_match_index].item()
                
                if max_similarity > threshold:
                    results.append({
                        'text': text,
                        'answer': self.answers[best_match_index],
                        'question': self.questions[best_match_index],
                        'similarity': float(max_similarity),
                        'index': int(best_match_index)
                    })
                else:
                    results.append(None)
            
            return results
            
        except Exception as e:
            print(f"批量匹配时出错: {e}")
            return [None] * len(texts)

    def find_similar_questions(self, text: str, threshold: float = 0.5, max_results: int = 5) -> List[Dict]:
        """
        查找所有相似的问题
        
        Args:
            text: 输入文本
            threshold: 相似度阈值
            max_results: 最大返回结果数
            
        Returns:
            相似问题列表
        """
        if not text or not text.strip():
            return []
            
        try:
            text_embedding = self.model.encode(text.strip(), convert_to_tensor=True)
            similarities = util.cos_sim(text_embedding, self.question_embeddings)[0]
            
            # 获取所有高于阈值的结果
            valid_indices = torch.where(similarities > threshold)[0]
            
            if len(valid_indices) == 0:
                return []
            
            # 按相似度排序
            valid_similarities = similarities[valid_indices]
            sorted_indices = torch.argsort(valid_similarities, descending=True)
            
            results = []
            for i in range(min(max_results, len(sorted_indices))):
                idx = valid_indices[sorted_indices[i]]
                similarity = similarities[idx].item()
                
                results.append({
                    'question': self.questions[idx],
                    'answer': self.answers[idx],
                    'similarity': float(similarity),
                    'index': int(idx)
                })
            
            return results
            
        except Exception as e:
            print(f"查找相似问题时出错: {e}")
            return []

    def get_stats(self) -> Dict:
        """获取知识库统计信息"""
        return {
            'total_questions': len(self.questions),
            'embedding_dimension': self.model.get_sentence_embedding_dimension(),
            'model_name': self.model_name,
            'cache_dir': self.cache_dir,
            'device': str(self.model.device)
        }

    def clear_cache(self):
        """清理缓存文件"""
        cache_path = self._get_cache_path()
        if os.path.exists(cache_path):
            os.remove(cache_path)
            print(f"缓存文件已删除: {cache_path}")
        else:
            print("没有找到缓存文件")

    def update_knowledge_base(self, knowledge_base_path: str):
        """更新知识库"""
        self.knowledge_base_path = knowledge_base_path
        self._load_knowledge_base()
        self._load_or_compute_embeddings()
        print("知识库更新完成！")


# 使用示例
if __name__ == "__main__":
    # 初始化匹配器
    matcher = SemanticQuestionMatcher(
        knowledge_base_path="knowledge_base.xlsx",
        model_name='paraphrase-multilingual-MiniLM-L12-v2'  # 或使用中文专用模型
    )
    
    # 单个匹配
    result = matcher.match("你好", threshold=0.6)
    if result:
        print(f"答案: {result['answer']}")
        print(f"相似度: {result['similarity']:.3f}")
    
    # 查找相似问题
    similar = matcher.find_similar_questions("如何使用", threshold=0.5, max_results=3)
    for item in similar:
        print(f"问题: {item['question']}, 相似度: {item['similarity']:.3f}")
    
    # 获取统计信息
    stats = matcher.get_stats()
    print(f"统计信息: {stats}")