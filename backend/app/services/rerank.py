"""Reranking via a small ONNX cross-encoder (no torch / no CUDA).

Model: cross-encoder/ms-marco-MiniLM-L-6-v2 qint8_arm64 ONNX, downloaded to HDD
models/reranker-minilm. CPU-efficient; used behind the RERANK_SEARCH capability.
"""
import os

_MODEL_DIR = "/mnt/jellyfin/Projects/NOMOS/models/reranker-minilm"
_ONNX = os.path.join(_MODEL_DIR, "onnx", "model_qint8_arm64.onnx")

_session = None
_tokenizer = None


def _load():
    global _session, _tokenizer
    if _session is not None:
        return _session, _tokenizer
    import onnxruntime as ort
    from transformers import BertTokenizerFast

    _session = ort.InferenceSession(_ONNX, providers=["CPUExecutionProvider"])
    _tokenizer = BertTokenizerFast.from_pretrained(_MODEL_DIR)
    return _session, _tokenizer


def RERANK_router(query: str, docs: list[str]) -> list[dict]:
    """Score (query, doc) pairs with the cross-encoder. Higher = more relevant.

    Returns [{'doc':..., 'score': float}, ...] ranked descending.
    """
    sess, tok = _load()
    pairs = [[query, d] for d in docs]
    enc = tok(pairs, padding=True, truncation=True, max_length=512, return_tensors="np")
    names = [i.name for i in sess.get_inputs()]
    feeds = {names[0]: enc["input_ids"], names[1]: enc["attention_mask"]}
    if "token_type_ids" in names:
        feeds["token_type_ids"] = enc["token_type_ids"]
    logits = sess.run(None, feeds)[0]
    if logits.shape[1] >= 2:
        rel = logits[:, 1]
    else:  # single relevance logit
        rel = logits[:, 0]
    scores = rel.tolist()
    ranked = sorted(zip(docs, scores), key=lambda x: x[1], reverse=True)
    return [{"doc": d, "score": float(s)} for d, s in ranked]