import numpy as np

def retrieve_sparse_bm25(bm25, tokenize_fn, query: str, top_k: int):
    q_tokens = tokenize_fn(query)
    scores = bm25.get_scores(q_tokens)
    top_ids = np.argsort(scores)[::-1][:top_k]
    return [(int(i), float(scores[i])) for i in top_ids]

def retrieve_dense_hnsw(embedder, faiss_store, query: str, top_k: int):
    q_vec = embedder.encode([query])  # (1, dim)
    scores, ids = faiss_store.search(q_vec.astype("float32"), top_k)
    return [(int(i), float(s)) for i, s in zip(ids[0], scores[0])]

def rrf_fuse(sparse_ranked, dense_ranked, k: int = 60):
    fused = {}
    for rank, (idx, _) in enumerate(sparse_ranked, start=1):
        fused[idx] = fused.get(idx, 0.0) + 1.0 / (k + rank)
    for rank, (idx, _) in enumerate(dense_ranked, start=1):
        fused[idx] = fused.get(idx, 0.0) + 1.0 / (k + rank)
    return fused

def dedupe_by_source(results, max_per_doc=2):
    counts, out = {}, []
    for r in results:
        src = r["source"]
        counts[src] = counts.get(src, 0) + 1
        if counts[src] <= max_per_doc:
            out.append(r)
    return out

def hybrid_retrieve(
    query: str,
    chunks,
    bm25,
    tokenize_fn,
    embedder,
    faiss_store,
    bm25_k: int,
    dense_k: int,
    final_k: int,
    rrf_k: int,
    max_per_doc: int
):
    sparse = retrieve_sparse_bm25(bm25, tokenize_fn, query, bm25_k)
    dense  = retrieve_dense_hnsw(embedder, faiss_store, query, dense_k)

    fused_scores = rrf_fuse(sparse, dense, k=rrf_k)

    sparse_rank = {idx: r+1 for r, (idx, _) in enumerate(sparse)}
    dense_rank  = {idx: r+1 for r, (idx, _) in enumerate(dense)}

    ranked = sorted(fused_scores.items(), key=lambda x: x[1], reverse=True)

    expanded = []
    for idx, fscore in ranked[: max(final_k * 4, 50)]:
        c = chunks[idx]
        expanded.append({
            "chunk_index": idx,
            "fused_score": float(fscore),
            "bm25_rank": sparse_rank.get(idx),
            "dense_rank": dense_rank.get(idx),
            "chunk_id": c["chunk_id"],
            "strategy": c.get("strategy"),
            "source": c["source"],
            "text": c["text"]
        })

    expanded = dedupe_by_source(expanded, max_per_doc=max_per_doc)
    return expanded[:final_k]
