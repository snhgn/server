"""Context Engine（上下文管理）包。

独立负责 AI 对话的上下文组装：
- tokens.py   轻量 Token 估算（无外部依赖）
- models.py   模型上下文窗口注册表（GLM / Gemini，支持环境变量覆盖）
- builder.py  ContextBuilder：按优先级组装 + Token 预算内自动压缩

与数据层（memory / rag）解耦：builder 只接收组装好的文本片段，
所有 user_id 隔离由调用方在检索时保证。
"""
