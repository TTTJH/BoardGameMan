# 🔧 ChromaDB 嵌入函数接口修复

## 问题描述

**错误信息**:
```
Expected EmbeddingFunction.__call__ to have the following signature: 
odict_keys(['self', 'input']), got odict_keys(['self', 'args', 'kwargs'])
```

**HTTP 状态**: 400 Bad Request
**端点**: POST /api/games/

## 根本原因

ChromaDB 0.4.21 版本更新了 `EmbeddingFunction` 接口规范。新版本要求：

- ✅ 正确: `__call__(self, input)` - 接收 `input` 参数
- ❌ 错误: `__call__(self, *args, **kwargs)` - 使用可变参数

之前的实现使用了简单的函数包装，不符合新的接口规范。

## 解决方案

### 修改文件: `app/services/vector_store.py`

**修改前**:
```python
def _get_embedding_function(self):
    """Get embedding function for ChromaDB"""
    def embed_fn(texts):
        return self.embedding_service.embed_texts(texts)
    return embed_fn
```

**修改后**:
```python
def _get_embedding_function(self):
    """Get embedding function for ChromaDB"""
    class CustomEmbeddingFunction:
        def __init__(self, embedding_service):
            self.embedding_service = embedding_service
        
        def __call__(self, input):
            """ChromaDB expects __call__ with 'input' parameter"""
            if isinstance(input, str):
                return [self.embedding_service.embed_text(input)]
            elif isinstance(input, list):
                return self.embedding_service.embed_texts(input)
            else:
                raise ValueError(f"Unexpected input type: {type(input)}")
    
    return CustomEmbeddingFunction(self.embedding_service)
```

## 关键改进

1. **正确的接口签名**
   - 使用 `__call__(self, input)` 而不是 `*args, **kwargs`
   - 符合 ChromaDB 0.4.21+ 的要求

2. **类型处理**
   - 支持单个字符串输入
   - 支持列表输入
   - 返回正确的格式

3. **向后兼容**
   - 保持与现有代码的兼容性
   - 不需要修改其他服务

## 验证结果

### ✅ API 测试

**请求**:
```bash
POST /api/games/
Content-Type: application/json

{
  "name": "Test Game",
  "description": "Test Description"
}
```

**响应**:
```
HTTP/1.1 201 Created
Content-Type: application/json

{
  "id": 6,
  "name": "Test Game",
  "description": "Test Description",
  "created_at": "2026-05-31T13:02:38",
  "updated_at": "2026-05-31T13:02:38"
}
```

### ✅ 前端验证

- ✓ 游戏列表加载成功
- ✓ 新游戏显示在列表中
- ✓ 所有组件正常渲染

## 相关文档

- [ChromaDB 嵌入函数文档](https://docs.trychroma.com/embeddings)
- [ChromaDB 迁移指南](https://docs.trychroma.com/migration#migration-to-0416---november-7-2023)

## 后续步骤

1. ✅ 修复嵌入函数接口
2. ✅ 重启后端服务
3. ✅ 验证 API 功能
4. ✅ 验证前端显示
5. 📋 继续使用系统

## 总结

通过实现符合 ChromaDB 新接口规范的 `CustomEmbeddingFunction` 类，成功解决了 400 Bad Request 错误。系统现已恢复正常运行。

**状态**: ✅ 已修复
**测试**: ✅ 已通过
**系统**: 🟢 正常运行
