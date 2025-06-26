# matcher.py
import pandas as pd
import jieba
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

class QuestionMatcher:
    def __init__(self, knowledge_base_path):
        try:
            # 1. 加载知识库
            df = pd.read_excel(knowledge_base_path)
            if 'question' not in df.columns or 'answer' not in df.columns:
                raise ValueError("Excel文件必须包含 'question' 和 'answer' 两列")
            
            self.questions = df['question'].dropna().tolist()
            self.answers = df['answer'].dropna().tolist()
            
            if len(self.questions) == 0:
                raise ValueError("知识库中没有有效的问题")
            
            # 2. 预处理和向量化
            self.vectorizer = TfidfVectorizer(
                tokenizer=self._chinese_tokenizer,
                lowercase=True,
                max_features=10000,
                ngram_range=(1, 2)  # 使用1-2元组合
            )
            self.question_vectors = self.vectorizer.fit_transform(self.questions)
            print(f"知识库加载完成！共加载 {len(self.questions)} 个问题")
            
        except FileNotFoundError:
            print(f"错误：找不到知识库文件 {knowledge_base_path}")
            print("请确保文件存在并且路径正确")
            raise
        except Exception as e:
            print(f"加载知识库时出错: {e}")
            raise

    def _chinese_tokenizer(self, text):
        """中文分词器"""
        if not text or not isinstance(text, str):
            return []
        # 使用jieba进行中文分词
        words = list(jieba.cut(text.strip()))
        # 过滤掉空字符串和单字符标点
        return [word for word in words if len(word.strip()) > 0]

    def match(self, text, threshold=0.15):
        """
        匹配最相似的问题
        :param text: 语音识别出的文本
        :param threshold: 相似度阈值，降低到0.15以提高匹配率
        :return: 匹配到的答案，如果没有则返回None
        """
        if not text or not text.strip():
            return None
            
        try:
            # 将输入文本向量化
            text_vector = self.vectorizer.transform([text.strip()])
            
            # 计算余弦相似度
            similarities = cosine_similarity(text_vector, self.question_vectors).flatten()
            
            # 找到最相似的问题
            best_match_index = np.argmax(similarities)
            max_similarity = similarities[best_match_index]
            
            matched_question = self.questions[best_match_index]
            
            print(f"识别文本: '{text}'")
            print(f"最匹配问题: '{matched_question}'")
            print(f"相似度: {max_similarity:.3f}")

            if max_similarity > threshold:
                return {
                    'answer': self.answers[best_match_index],
                    'question': matched_question,
                    'similarity': float(max_similarity)
                }
            else:
                print(f"相似度 {max_similarity:.3f} 低于阈值 {threshold}，未找到匹配")
            
        except Exception as e:
            print(f"匹配时出错: {e}")
        
        return None

    def get_stats(self):
        """获取知识库统计信息"""
        return {
            'total_questions': len(self.questions),
            'vocabulary_size': len(self.vectorizer.get_feature_names_out()) if hasattr(self.vectorizer, 'get_feature_names_out') else 'Unknown'
        }