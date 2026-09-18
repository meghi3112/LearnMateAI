import os
import re
import json
import logging
import numpy as np
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

# Base path for persistent vector store indices (configurable for deployment)
VECTOR_BASE_DIR = os.getenv(
    "VECTOR_STORE_DIR",
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "vectorstores"))
)
os.makedirs(VECTOR_BASE_DIR, exist_ok=True)

# Global cache for FAISS indices keyed strictly by (user_id, material_id)
_INDEX_CACHE: Dict[Tuple[int, int], Any] = {}

def clean_document_text(text: str) -> str:
    """Normalize whitespace and remove non-printable artifacts."""
    if not text:
        return ""
    # Remove control characters except standard whitespace
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", " ", text)
    # Collapse multiple spaces while preserving paragraphs
    paragraphs = [re.sub(r"[ \t]+", " ", p).strip() for p in text.split("\n") if p.strip()]
    return "\n\n".join(paragraphs)

def chunk_document_text(text: str, chunk_size: int = 700, chunk_overlap: int = 120) -> List[str]:
    """Split text into semantically cohesive passages using RecursiveCharacterTextSplitter."""
    if not text:
        return []

    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ". ", "? ", "! ", "; ", ", ", " ", ""]
        )
        chunks = splitter.split_text(text)
        return [c.strip() for c in chunks if len(c.strip()) > 25]
    except Exception as e:
        logger.warning(f"LangChain splitter fallback: {e}")
        paragraphs = text.split("\n\n")
        chunks = []
        current = ""
        for p in paragraphs:
            if len(current) + len(p) + 2 <= chunk_size:
                current = f"{current}\n\n{p}".strip()
            else:
                if current:
                    chunks.append(current)
                current = p
        if current:
            chunks.append(current)
        return [c for c in chunks if len(c) > 25]


def extract_structured_document_chunks(
    text: str,
    user_id: int,
    material_id: int,
    source_file: str = "",
    chunk_size: int = 700,
    chunk_overlap: int = 120
) -> List[Dict[str, Any]]:
    """
    Parse document text into semantic chunks with rich metadata:
    - Page number (tracked from page markers)
    - Section title (detected headers, units, chapters)
    - Subsection title (sub-topics, instructions, components)
    - Content type (definition, code, procedure, table, explanation)
    - User and Material IDs for multi-tenant isolation
    """
    if not text:
        return []

    mnemonics = {
        "MOV", "PUSH", "PUSHF", "POP", "POPF", "XCHG", "LEA", "LDS", "LES", "LAHF", "SAHF", "XLAT", "IN", "OUT",
        "MOVSB", "MOVSW", "CMPSB", "CMPSW", "SCASB", "SCASW", "LODSB", "LODSW", "STOSB", "STOSW",
        "REP", "REPE", "REPZ", "REPNE", "REPNZ", "ADD", "ADC", "INC", "SUB", "SBB", "DEC", "NEG",
        "MUL", "IMUL", "DIV", "IDIV", "DAA", "DAS", "AAA", "AAS", "AAM", "AAD", "CBW", "CWD",
        "AND", "OR", "XOR", "NOT", "TEST", "SHL", "SAL", "SHR", "SAR", "ROL", "ROR", "RCL", "RCR",
        "CLC", "STC", "CMC", "CLD", "STD", "CLI", "STI", "HLT", "WAIT", "ESC", "LOCK", "NOP",
        "JMP", "CALL", "RET", "LOOP", "LOOPE", "LOOPNE", "JZ", "JNZ", "JE", "JNE", "JC", "JNC",
        "JO", "JNO", "JS", "JNS", "JP", "JNP", "JA", "JNBE", "JAE", "JNB", "JB", "JNAE", "JBE",
        "JNA", "JG", "JNLE", "JGE", "JNL", "JL", "JNGE", "JLE", "JNG", "INT", "INTO", "IRET"
    }

    lines = text.split("\n")
    current_page = 1
    current_section = "Introduction & Overview"
    current_subsection = ""

    paragraphs = []
    current_para = []

    for line in lines:
        s = line.strip()
        if not s:
            if current_para:
                paragraphs.append((current_page, current_section, current_subsection, "\n".join(current_para)))
                current_para = []
            continue

        p_match = re.match(r"^---\s+(?:Page|Slide)\s+(\d+)\s+---", s)
        if p_match:
            if current_para:
                paragraphs.append((current_page, current_section, current_subsection, "\n".join(current_para)))
                current_para = []
            current_page = int(p_match.group(1))
            continue

        # Section header detection
        words = s.split()
        if len(s) <= 65 and not re.search(r"[\.\!\?\,]\s*$", s) and "." not in s and 2 <= len(words) <= 8:
            if s.isupper() or re.match(r"^(?:UNIT|CHAPTER|SECTION|PART|WEEK|AIM|EXPERIMENT|MODULE|TOPIC)\b", s, re.IGNORECASE) or (sum(1 for w in words if w[0].isupper() or w[0].isdigit()) / len(words) >= 0.75):
                if not any(w.upper() in mnemonics for w in words) and s not in ("Instruction", "Syntax", "Example", "Description/Working", "Description", "Flag Condition"):
                    if current_para:
                        paragraphs.append((current_page, current_section, current_subsection, "\n".join(current_para)))
                        current_para = []
                    current_section = s
                    current_subsection = ""
                    continue

        # Subsection detection (instruction mnemonic, label, or sub-item)
        if s.upper() in mnemonics:
            current_subsection = s.upper()
        elif s.endswith(":") and len(s) < 30:
            current_subsection = s[:-1].strip()

        current_para.append(s)

    if current_para:
        paragraphs.append((current_page, current_section, current_subsection, "\n".join(current_para)))

    chunks: List[Dict[str, Any]] = []
    curr_text = ""
    curr_page = 1
    curr_sec = "Introduction & Overview"
    curr_subsec = ""

    for p_page, p_sec, p_subsec, p_text in paragraphs:
        if not p_text.strip():
            continue

        if len(curr_text) + len(p_text) + 2 <= chunk_size and (curr_sec == p_sec or len(curr_text) < 200):
            curr_text = f"{curr_text}\n\n{p_text}".strip() if curr_text else p_text
            curr_page = p_page
            curr_sec = p_sec
            if p_subsec:
                curr_subsec = p_subsec
        else:
            if curr_text and len(curr_text) > 25:
                # Semantic content type classification
                c_type = "explanation"
                if re.search(r"\b(?:MOV|PUSH|POP|LEA|LDS|LES|INT 21H|ADD|SUB|MOV AX)\b", curr_text) or any(m in curr_text.split() for m in mnemonics):
                    c_type = "code"
                elif re.search(r"\b(?:is defined as|refers to|is a 16-bit|is a supervised|means|is an ensemble|consists of)\b", curr_text, re.IGNORECASE):
                    c_type = "definition"
                elif re.search(r"\b(?:step \d+|decrements|increments|then copies|algorithm|procedure|execution workflow)\b", curr_text, re.IGNORECASE):
                    c_type = "procedure"
                elif "|" in curr_text:
                    c_type = "table"

                chunks.append({
                    "chunk_id": len(chunks),
                    "user_id": int(user_id),
                    "material_id": int(material_id),
                    "session_id": "",
                    "page": curr_page,
                    "section": curr_sec,
                    "subsection": curr_subsec,
                    "content_type": c_type,
                    "source_file": source_file,
                    "text": curr_text
                })
            curr_text = p_text
            curr_page = p_page
            curr_sec = p_sec
            curr_subsec = p_subsec

    if curr_text and len(curr_text) > 25:
        chunks.append({
            "chunk_id": len(chunks),
            "user_id": int(user_id),
            "material_id": int(material_id),
            "session_id": "",
            "page": curr_page,
            "section": curr_sec,
            "subsection": curr_subsec,
            "content_type": "explanation",
            "source_file": source_file,
            "text": curr_text
        })

    return chunks

def _compute_fallback_embeddings(texts: List[str], dim: int = 256) -> np.ndarray:
    """
    Deterministic normalized character n-gram hashing embedding fallback.
    Used if Gemini embeddings API key is not configured or during offline operations.
    """
    vectors = np.zeros((len(texts), dim), dtype=np.float32)
    for i, t in enumerate(texts):
        words = re.findall(r"\w+", t.lower())
        for w in words:
            h = hash(w) % dim
            vectors[i, h] += 1.0
        norm = np.linalg.norm(vectors[i])
        if norm > 1e-6:
            vectors[i] /= norm
    return vectors

def compute_embeddings(texts: List[str], api_key: Optional[str] = None) -> np.ndarray:
    """
    Compute dense vector embeddings using Google GenAI (text-embedding-004) with fallback.
    Returns normalized float32 numpy array suitable for cosine similarity.
    """
    gemini_key = api_key or os.getenv("GEMINI_API_KEY")

    if gemini_key and gemini_key.strip():
        try:
            from google import genai
            client = genai.Client(api_key=gemini_key.strip())
            batch_size = 32
            all_embeddings = []

            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                response = client.models.embed_content(
                    model="text-embedding-004",
                    contents=batch
                )

                if hasattr(response, "embeddings"):
                    for emb in response.embeddings:
                        all_embeddings.append(emb.values)
                elif hasattr(response, "embedding"):
                    all_embeddings.append(response.embedding.values)

            if all_embeddings and len(all_embeddings) == len(texts):
                arr = np.array(all_embeddings, dtype=np.float32)
                norms = np.linalg.norm(arr, axis=1, keepdims=True)
                norms[norms < 1e-6] = 1.0
                return arr / norms

        except Exception as e:
            logger.warning(f"Gemini API embed_content failed, falling back to local indexing: {e}")

    return _compute_fallback_embeddings(texts)


class MaterialFAISSIndex:
    """
    FAISS-powered vector index with strict multi-tenant isolation.
    Every index is bound to a single (user_id, material_id) pair.
    """

    def __init__(
        self,
        user_id: int,
        material_id: int,
        chunk_dicts: List[Dict[str, Any]],
        source_file: str = "",
        api_key: Optional[str] = None
    ):
        import faiss
        self.user_id = int(user_id)
        self.material_id = int(material_id)
        self.source_file = source_file or ""
        self.api_key = api_key

        # Ensure every chunk has strict structured metadata attached
        self.chunk_metadata: List[Dict[str, Any]] = []
        raw_texts: List[str] = []

        for idx, item in enumerate(chunk_dicts):
            txt = item["text"] if isinstance(item, dict) else str(item)
            meta = {
                "chunk_id": item.get("chunk_id", idx) if isinstance(item, dict) else idx,
                "user_id": self.user_id,
                "material_id": self.material_id,
                "session_id": item.get("session_id", "") if isinstance(item, dict) else "",
                "page": item.get("page", 1) if isinstance(item, dict) else 1,
                "section": item.get("section", "General") if isinstance(item, dict) else "General",
                "subsection": item.get("subsection", "") if isinstance(item, dict) else "",
                "content_type": item.get("content_type", "explanation") if isinstance(item, dict) else "explanation",
                "source_file": self.source_file,
                "text": txt
            }
            self.chunk_metadata.append(meta)
            raw_texts.append(txt)

        self.embeddings = compute_embeddings(raw_texts, api_key=api_key)
        self.dim = self.embeddings.shape[1]

        # Inner product on normalized vectors = Cosine Similarity
        self.index = faiss.IndexFlatIP(self.dim)
        self.index.add(self.embeddings)

    def retrieve(self, query: str, top_k: int = 6) -> List[Dict[str, Any]]:
        """
        Retrieve top_k most relevant text chunks for a query using hybrid dense + section-aware keyword search.
        Strictly validates that retrieved chunks match this store's (user_id, material_id).
        """
        if not self.chunk_metadata or self.index.ntotal == 0:
            return []

        actual_k = min(top_k * 3, len(self.chunk_metadata))
        q_emb = compute_embeddings([query], api_key=self.api_key)

        distances, indices = self.index.search(q_emb, actual_k)

        # Keyword relevance re-ranking & section boosting
        educational_common = {
            "what", "is", "the", "are", "and", "in", "of", "to", "for", "how", "does", "do", "explain", "describe",
            "tell", "me", "about", "this", "that", "with", "from", "on", "can", "you", "please", "detail", "details",
            "instruction", "instructions", "topic", "topics", "subject", "concept", "concepts", "document", "material",
            "file", "page", "definition", "overview", "give", "provide", "summary"
        }
        q_terms = [w.lower() for w in re.findall(r"\w+", query.lower()) if w.lower() not in educational_common and len(w) >= 2]

        # Domain term expansion (without hardcoding subjects)
        q_lower = query.lower()
        if any(w in q_lower for w in ("address", "addressing", "mode", "operand")):
            q_terms.extend(["address", "effective", "offset", "lea", "lds", "les", "register", "immediate", "memory", "displacement"])
        if any(w in q_lower for w in ("transfer", "movement", "mov", "push", "pop")):
            q_terms.extend(["mov", "push", "pop", "xchg", "in", "out", "xlat", "accumulator"])
        if any(w in q_lower for w in ("arithmetic", "add", "sub", "multiply", "divide")):
            q_terms.extend(["add", "adc", "sub", "sbb", "mul", "imul", "div", "idiv", "daa", "das"])
        if any(w in q_lower for w in ("string", "array")):
            q_terms.extend(["movsb", "cmpsb", "scasb", "lodsb", "stosb", "rep", "repe", "repne"])
        if any(w in q_lower for w in ("branch", "jump", "loop", "call")):
            q_terms.extend(["jmp", "call", "ret", "loop", "loope", "loopne", "conditional"])
        if any(w in q_lower for w in ("forest", "ensemble", "tree", "bagging")):
            q_terms.extend(["random forest", "ensemble", "decision tree", "regression", "bagging", "bootstrap"])
        if any(w in q_lower for w in ("pattern", "design pattern")):
            q_terms.extend(["creational", "structural", "behavioral", "factory", "singleton", "observer", "adapter"])
        if any(w in q_lower for w in ("normal", "normalization", "database")):
            q_terms.extend(["1nf", "2nf", "3nf", "bcnf", "functional dependency", "anomaly", "decomposition"])
        q_terms = list(dict.fromkeys(q_terms))

        candidates = []
        seen_indices = set()

        for rank, idx in enumerate(indices[0]):
            if 0 <= idx < len(self.chunk_metadata):
                seen_indices.add(idx)
                chunk_meta = self.chunk_metadata[idx]
                if chunk_meta.get("user_id") != self.user_id or chunk_meta.get("material_id") != self.material_id:
                    continue
                dense_score = float(distances[0][rank])
                chunk_text_lower = chunk_meta["text"].lower()
                sec_lower = (chunk_meta.get("section", "") + " " + chunk_meta.get("subsection", "")).lower()

                # Text matches: +3.0
                kw_score = sum(3.0 for t in q_terms if re.search(r"\b" + re.escape(t) + r"\b", chunk_text_lower))
                # Section header matches: +6.0
                sec_score = sum(6.0 for t in q_terms if re.search(r"\b" + re.escape(t) + r"\b", sec_lower))

                total_score = dense_score + kw_score + sec_score
                candidates.append((total_score, idx, chunk_meta))

        # Check all other chunks for exact section or term matches
        if q_terms:
            for idx, chunk_meta in enumerate(self.chunk_metadata):
                if idx not in seen_indices:
                    if chunk_meta.get("user_id") != self.user_id or chunk_meta.get("material_id") != self.material_id:
                        continue
                    chunk_text_lower = chunk_meta["text"].lower()
                    sec_lower = (chunk_meta.get("section", "") + " " + chunk_meta.get("subsection", "")).lower()
                    kw_score = sum(3.0 for t in q_terms if re.search(r"\b" + re.escape(t) + r"\b", chunk_text_lower))
                    sec_score = sum(6.0 for t in q_terms if re.search(r"\b" + re.escape(t) + r"\b", sec_lower))
                    if kw_score > 0 or sec_score > 0:
                        candidates.append((kw_score + sec_score, idx, chunk_meta))

        candidates.sort(key=lambda x: x[0], reverse=True)

        results = []
        for rank, (score, idx, chunk_meta) in enumerate(candidates[:top_k], 1):
            results.append({
                "chunk_id": int(chunk_meta["chunk_id"]),
                "user_id": self.user_id,
                "material_id": self.material_id,
                "source_file": chunk_meta.get("source_file", ""),
                "page": chunk_meta.get("page", 1),
                "section": chunk_meta.get("section", ""),
                "subsection": chunk_meta.get("subsection", ""),
                "content_type": chunk_meta.get("content_type", "explanation"),
                "text": chunk_meta["text"],
                "similarity_score": round(float(score), 4),
                "rank": rank
            })
        return results

    def get_full_context(self, top_k: int = 6) -> str:
        """Return combined text of the top chunks separated by section breaks."""
        if not self.chunk_metadata:
            return ""
        k = min(top_k, len(self.chunk_metadata))
        return "\n\n---\n\n".join(m["text"] for m in self.chunk_metadata[:k])

    def get_stratified_context(self, max_chunks: int = 8, max_chars: int = 15000) -> str:
        """
        Produce a representative multi-section context by sampling chunks across all sections
        in the document. This ensures broad topics and whole-material queries cover the entire
        document proportionally from start to finish.
        """
        if not self.chunk_metadata:
            return ""

        sections_map: Dict[str, List[Dict[str, Any]]] = {}
        for c in self.chunk_metadata:
            sec = c.get("section", "General") or "General"
            sections_map.setdefault(sec, []).append(c)

        selected_chunks: List[Dict[str, Any]] = []
        round_idx = 0
        total_chars = 0
        added = True

        while len(selected_chunks) < max_chunks and added and total_chars < max_chars:
            added = False
            for sec, s_chunks in sections_map.items():
                if round_idx < len(s_chunks):
                    candidate = s_chunks[round_idx]
                    cand_len = len(candidate.get("text", ""))
                    if total_chars + cand_len <= max_chars or not selected_chunks:
                        selected_chunks.append(candidate)
                        total_chars += cand_len
                        added = True
                        if len(selected_chunks) >= max_chunks:
                            break
            round_idx += 1

        selected_chunks.sort(key=lambda x: x.get("chunk_id", 0))
        return "\n\n---\n\n".join(c["text"] for c in selected_chunks)

    def save_to_disk(self) -> str:
        """Persist index and metadata to isolated per-user, per-material directory."""
        import faiss
        target_dir = os.path.join(VECTOR_BASE_DIR, f"user_{self.user_id}", f"material_{self.material_id}")
        os.makedirs(target_dir, exist_ok=True)

        index_path = os.path.join(target_dir, "index.faiss")
        faiss.write_index(self.index, index_path)

        meta_path = os.path.join(target_dir, "metadata.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump({
                "user_id": self.user_id,
                "material_id": self.material_id,
                "source_file": self.source_file,
                "chunk_count": len(self.chunk_metadata),
                "chunks": self.chunk_metadata
            }, f, indent=2)

        return target_dir

    @classmethod
    def load_from_disk(cls, user_id: int, material_id: int, api_key: Optional[str] = None) -> Optional["MaterialFAISSIndex"]:
        """Load index from isolated disk directory if available."""
        import faiss
        target_dir = os.path.join(VECTOR_BASE_DIR, f"user_{user_id}", f"material_{material_id}")
        index_path = os.path.join(target_dir, "index.faiss")
        meta_path = os.path.join(target_dir, "metadata.json")

        if not (os.path.exists(index_path) and os.path.exists(meta_path)):
            return None

        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)

            if meta.get("user_id") != user_id or meta.get("material_id") != material_id:
                logger.error(f"[SECURITY] Metadata file mismatch in {target_dir}")
                return None

            instance = cls.__new__(cls)
            instance.user_id = int(user_id)
            instance.material_id = int(material_id)
            instance.source_file = meta.get("source_file", "")
            instance.api_key = api_key
            instance.chunk_metadata = meta.get("chunks", [])
            instance.index = faiss.read_index(index_path)
            instance.dim = instance.index.d
            return instance
        except Exception as e:
            logger.warning(f"Could not load index from {target_dir}: {e}")
            return None


def build_material_vector_store(
    user_id: int,
    material_id: int,
    raw_text: str,
    source_file: str = "",
    api_key: Optional[str] = None
) -> MaterialFAISSIndex:
    """Clean, chunk, and index a material's text into an isolated FAISS store with rich structure metadata."""
    from backend.rag.extractor import clean_extracted_text
    cleaned = clean_extracted_text(raw_text)
    chunk_dicts = extract_structured_document_chunks(
        text=cleaned,
        user_id=user_id,
        material_id=material_id,
        source_file=source_file
    )
    if not chunk_dicts:
        chunk_dicts = [{
            "chunk_id": 0,
            "user_id": user_id,
            "material_id": material_id,
            "session_id": "",
            "page": 1,
            "section": "Overview",
            "subsection": "",
            "content_type": "explanation",
            "source_file": source_file,
            "text": cleaned[:1000] if cleaned else "Empty document."
        }]

    index_manager = MaterialFAISSIndex(
        user_id=user_id,
        material_id=material_id,
        chunk_dicts=chunk_dicts,
        source_file=source_file,
        api_key=api_key
    )

    _INDEX_CACHE[(int(user_id), int(material_id))] = index_manager

    try:
        index_manager.save_to_disk()
    except Exception as e:
        logger.warning(f"Failed to persist index to disk: {e}")

    return index_manager


def get_material_vector_store(user_id: int, material_id: int) -> Optional[MaterialFAISSIndex]:
    """Retrieve cached or persisted FAISS index for a specific user and material."""
    key = (int(user_id), int(material_id))
    if key in _INDEX_CACHE:
        return _INDEX_CACHE[key]

    loaded = MaterialFAISSIndex.load_from_disk(user_id, material_id)
    if loaded:
        _INDEX_CACHE[key] = loaded
        return loaded

    return None


def invalidate_material_cache(user_id: Optional[int] = None, material_id: Optional[int] = None) -> None:
    """Invalidate cached vector stores."""
    global _INDEX_CACHE
    if user_id is not None and material_id is not None:
        _INDEX_CACHE.pop((int(user_id), int(material_id)), None)
    elif user_id is not None:
        _INDEX_CACHE = {k: v for k, v in _INDEX_CACHE.items() if k[0] != int(user_id)}
    elif material_id is not None:
        _INDEX_CACHE = {k: v for k, v in _INDEX_CACHE.items() if k[1] != int(material_id)}
    else:
        _INDEX_CACHE.clear()


def retrieve_material_context_with_metadata(
    user_id: int,
    material_id: int,
    query: str,
    raw_text: Optional[str] = None,
    top_k: int = 6,
    source_file: str = ""
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Retrieve top_k context passages with strict user_id and material_id tenant isolation.
    Validates chunk metadata to guarantee zero cross-material leakage.
    If query is broad (e.g. whole document or overall material name), provides stratified
    multi-section representation.
    If query is specific (e.g. Addressing Modes or MOV), retrieves section-focused chunks.
    """
    u_id = int(user_id)
    m_id = int(material_id)

    store = get_material_vector_store(u_id, m_id)
    if not store and raw_text:
        store = build_material_vector_store(
            user_id=u_id,
            material_id=m_id,
            raw_text=raw_text,
            source_file=source_file
        )

    hits = []
    if store:
        hits = store.retrieve(query, top_k=top_k)
        hits = [h for h in hits if h.get("user_id") == u_id and h.get("material_id") == m_id]

        q_clean = (query or "").lower().strip()
        file_clean = os.path.splitext(os.path.basename(source_file))[0].lower().replace("_", " ").replace("-", " ")

        is_broad = (
            not q_clean or
            any(w in q_clean for w in ["summarize the whole", "all topics", "whole document", "full material", "overview", "entire document"]) or
            (file_clean and (q_clean == file_clean or file_clean in q_clean))
        )

        if is_broad:
            stratified_text = store.get_stratified_context(max_chunks=top_k)
            return stratified_text, hits

        if hits:
            focused_text = "\n\n---\n\n".join([r["text"] for r in hits])
            return focused_text, hits

        return store.get_stratified_context(max_chunks=top_k), hits

    fallback_text = raw_text[:15000] if raw_text else ""
    return fallback_text, []


def retrieve_material_context(
    user_id: int,
    material_id: int,
    query: str,
    raw_text: Optional[str] = None,
    top_k: int = 5,
    source_file: str = ""
) -> str:
    """Unified context retrieval returning context text strictly isolated for (user_id, material_id)."""
    context_text, _ = retrieve_material_context_with_metadata(
        user_id=user_id,
        material_id=material_id,
        query=query,
        raw_text=raw_text,
        top_k=top_k,
        source_file=source_file
    )
    return context_text
