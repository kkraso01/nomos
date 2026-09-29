"""Replaceable embedding provider (EMBED_TEXT).

Domain logic depends only on embed(texts) -> vectors + meta(). The concrete
provider (multilingual-e5-small ONNX on HDD, initially) is swappable without
touching retrieval/chunk code. A DISABLED provider is returned when no model is
installed so nothing crashes.
"""
import math
import os

_MODEL_DIR = "/mnt/jellyfin/Projects/NOMOS/models/e5-small"
_ONNX = os.path.join(_MODEL_DIR, "onnx", "model.onnx")

_provider = None


class EmbeddingProvider:
    name = "disabled"
    model = ""
    version = ""
    dimensions = 0

    def meta(self) -> dict:
        return {"provider": self.name, "model": self.model, "version": self.version,
                "dimensions": self.dimensions}

    def available(self) -> bool:
        return False

    def embed(self, texts, is_query: bool = False):
        raise NotImplementedError


class DisabledEmbeddingProvider(EmbeddingProvider):
    def __init__(self):
        self.name = "none"


class OnnxE5EmbeddingProvider(EmbeddingProvider):
    def __init__(self, model_dir: str = _MODEL_DIR):
        import onnxruntime as ort
        from transformers import XLMRobertaTokenizerFast
        self.name = "onnx"
        self.model = "multilingual-e5-small"
        self.version = "intfloat-e5-small-v2-fp32"
        self.dimensions = 384
        self._session = ort.InferenceSession(_ONNX, providers=["CPUExecutionProvider"])
        self._tok = XLMRobertaTokenizerFast.from_pretrained(model_dir)
        self._names = [i.name for i in self._session.get_inputs()]

    def available(self) -> bool:
        return True

    def embed(self, texts, is_query: bool = False):
        prefix = "query: " if is_query else "passage: "
        encoded = self._tok([prefix + (t or "") for t in texts], padding=True,
                            truncation=True, max_length=512, return_tensors="np")
        feeds = {self._names[0]: encoded["input_ids"],
                 self._names[1]: encoded["attention_mask"]}
        if "token_type_ids" in self._names:
            feeds["token_type_ids"] = encoded.get("token_type_ids") if encoded.get("token_type_ids") is not None \
                else __import__("numpy").zeros_like(encoded["input_ids"])
        out = self._session.run(["last_hidden_state"], feeds)[0]  # (B, seq, dim)
        mask = encoded["attention_mask"]
        # mean-pool over non-pad tokens
        sum_h = (out * mask[..., None]).sum(axis=1)          # (B, dim)
        counts = mask.sum(axis=1, keepdims=True).clip(min=1)
        pooled = sum_h / counts
        # L2 normalize
        norm = pooled / (pooled ** 2).sum(axis=1, keepdims=True) ** 0.5
        return norm.tolist()


def _build():
    global _provider
    if os.path.exists(_ONNX):
        try:
            _provider = OnnxE5EmbeddingProvider()
            return
        except Exception:  # noqa: BLE001
            _provider = DisabledEmbeddingProvider()
            return
    _provider = DisabledEmbeddingProvider()


def get_provider():
    global _provider
    if _provider is None:
        _build()
    return _provider


def cosine(a, b):
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return dot / (na * nb)