"""
机器学习模型训练脚本
使用逻辑回归训练点击预测模型
"""

import joblib
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, precision_score, recall_score, classification_report
from pathlib import Path
import sys

# 添加项目根目录到sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from ml.data_preprocessor import DataPreprocessor


def train_click_prediction_model():
    """
    训练点击预测模型
    """
    print("开始构建训练样本...")
    
    # 创建数据预处理器
    preprocessor = DataPreprocessor()
    
    # 构建训练样本
    X, y, feature_names = preprocessor.build_training_samples()
    
    print(f"训练样本数量: {X.shape[0]}")
    print(f"特征数量: {X.shape[1]}")
    print(f"特征名称: {feature_names}")
    print(f"正样本比例: {np.mean(y):.3f}")
    
    # 划分训练集和测试集
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    
    print(f"训练集大小: {X_train.shape[0]}")
    print(f"测试集大小: {X_test.shape[0]}")
    
    # 特征标准化
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # 训练模型
    print("开始训练模型...")
    model = LogisticRegression(random_state=42, max_iter=1000)
    model.fit(X_train_scaled, y_train)
    
    # 预测
    y_pred = model.predict(X_test_scaled)
    y_pred_proba = model.predict_proba(X_test_scaled)[:, 1]
    
    # 评估模型
    accuracy = accuracy_score(y_test, y_pred)
    precision = precision_score(y_test, y_pred, zero_division=0)
    recall = recall_score(y_test, y_pred, zero_division=0)
    
    print("\n=== 模型评估结果 ===")
    print(f"准确率 (Accuracy): {accuracy:.4f}")
    print(f"精确率 (Precision): {precision:.4f}")
    print(f"召回率 (Recall): {recall:.4f}")
    
    print("\n详细分类报告:")
    print(classification_report(y_test, y_pred))
    
    # 保存模型和标准化器
    model_dir = Path(__file__).parent
    model_path = model_dir / 'click_model.pkl'
    scaler_path = model_dir / 'scaler.pkl'
    
    joblib.dump(model, model_path)
    joblib.dump(scaler, scaler_path)
    
    print(f"\n模型已保存至: {model_path}")
    print(f"标准化器已保存至: {scaler_path}")
    
    # 特征重要性
    feature_importance = abs(model.coef_[0])
    print("\n特征重要性:")
    for i, (name, importance) in enumerate(zip(feature_names, feature_importance)):
        print(f"  {name}: {importance:.4f}")
    
    return model, scaler, feature_names


if __name__ == "__main__":
    model, scaler, feature_names = train_click_prediction_model()