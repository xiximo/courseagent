# 向量模型目录（挂载到容器 `/app/models`）

把 `bge-small-zh-v1.5` 整目录上传到这里，**不要打进 Docker 镜像**。

## 目录结构

```
models/
  bge-small-zh-v1.5/
    config.json
    modules.json
    config_sentence_transformers.json
    sentence_bert_config.json
    tokenizer.json
    tokenizer_config.json
    vocab.txt
    special_tokens_map.json
    1_Pooling/config.json
    model.safetensors          # 或 pytorch_model.bin
```

本机若已有 `backend/models/bge-small-zh-v1.5`，上传示例：

```bash
scp -r backend/models/bge-small-zh-v1.5 root@你的服务器:/opt/courseagent/deploy/models/
```

上传后宿主机应能看到：

```bash
ls /opt/courseagent/deploy/models/bge-small-zh-v1.5/config.json
```

若放在其它路径，改 `deploy/.env` 的 `EMBEDDING_MODELS_DIR`。改完或补传模型后：

```bash
cd /opt/courseagent/deploy
docker compose restart backend
```
