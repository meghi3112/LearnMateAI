import os
import re
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

def ocr_pdf_pages(file_path: str, dpi: int = 150) -> str:
    """
    Perform high-resolution OCR on all pages of a PDF in sequential order.
    Uses native Windows OCR (winocr) with pytesseract fallback.
    Preserves sequential page markers and formatted text lines.
    """
    import pymupdf
    import io
    from PIL import Image

    text_parts = []
    try:
        with pymupdf.open(file_path) as doc:
            total_pages = len(doc)
            logger.info(f"[OCR] Starting sequential OCR for {total_pages} pages at {dpi} DPI: {file_path}")
            for page_num, page in enumerate(doc, start=1):
                try:
                    pix = page.get_pixmap(dpi=dpi)
                    img = Image.open(io.BytesIO(pix.tobytes("png")))
                    page_text = ""

                    # 1. Native Windows Media OCR (fast, high accuracy, local)
                    try:
                        import winocr
                        res = winocr.recognize_pil_sync(img)
                        if isinstance(res, dict):
                            lines = [l.get("text", "").strip() for l in res.get("lines", []) if l.get("text", "").strip()]
                            if lines:
                                page_text = "\n".join(lines)
                            elif res.get("text", "").strip():
                                page_text = res.get("text", "").strip()
                    except Exception as winocr_err:
                        logger.debug(f"[OCR] winocr failed on page {page_num}: {winocr_err}")

                    # 2. Pytesseract fallback if winocr produced no text or failed
                    if not page_text:
                        try:
                            import pytesseract
                            tess_text = pytesseract.image_to_string(img).strip()
                            if tess_text:
                                page_text = tess_text
                        except Exception as tess_err:
                            logger.debug(f"[OCR] pytesseract fallback failed on page {page_num}: {tess_err}")

                    if page_text:
                        text_parts.append(f"--- Page {page_num} ---\n{page_text}")
                        logger.info(f"[OCR] Page {page_num}/{total_pages} processed ({len(page_text)} chars).")
                    else:
                        logger.warning(f"[OCR] Page {page_num}/{total_pages} produced no readable text.")

                except Exception as page_err:
                    logger.error(f"[OCR] Error processing page {page_num} of {file_path}: {page_err}")
                    continue

        full_ocr_text = "\n\n".join(text_parts).strip()
        logger.info(f"[OCR] Completed OCR extraction for {file_path}: total {len(full_ocr_text)} chars across {len(text_parts)} pages.")
        return full_ocr_text
    except Exception as e:
        logger.error(f"[OCR] Fatal error during PDF OCR extraction for {file_path}: {e}", exc_info=True)
        return ""

def extract_text_from_pdf(file_path: str) -> str:
    """
    Extract clean text from a PDF file.
    Uses fast PyMuPDF selectable text extraction first (zero overhead for text PDFs).
    If selectable text is empty or insufficient (< max(60, pages * 10) chars),
    automatically falls back to sequential OCR processing.
    """
    import pymupdf
    text_parts = []
    total_pages = 0
    with pymupdf.open(file_path) as doc:
        total_pages = len(doc)
        for page_num, page in enumerate(doc, start=1):
            page_text = page.get_text("text")
            if page_text and page_text.strip():
                text_parts.append(f"--- Page {page_num} ---\n{page_text.strip()}")

    combined_text = "\n\n".join(text_parts).strip()
    min_meaningful_chars = max(60, total_pages * 10)

    # Check if selectable text is meaningful
    if len(combined_text) >= min_meaningful_chars:
        logger.info(f"[PDF Extractor] Selectable text found ({len(combined_text)} chars across {total_pages} pages). Zero OCR overhead.")
        return combined_text

    logger.info(
        f"[PDF Extractor] Selectable text insufficient ({len(combined_text)} chars for {total_pages} pages). "
        f"Treating as scanned/image-based PDF. Initiating sequential OCR fallback..."
    )
    return ocr_pdf_pages(file_path)

def extract_text_from_docx(file_path: str) -> str:
    """Extract paragraphs and table text from a DOCX file using python-docx."""
    import docx
    doc = docx.Document(file_path)
    text_parts = []

    # Extract paragraphs
    for p in doc.paragraphs:
        cleaned = p.text.strip()
        if cleaned:
            text_parts.append(cleaned)

    # Extract tables
    for table in doc.tables:
        for row in table.rows:
            row_cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if row_cells:
                text_parts.append(" | ".join(row_cells))

    return "\n\n".join(text_parts)

def extract_text_from_pptx(file_path: str) -> str:
    """Extract slide titles, body text, and tables from a PPTX presentation."""
    import pptx
    prs = pptx.Presentation(file_path)
    text_parts = []

    for slide_idx, slide in enumerate(prs.slides, start=1):
        slide_lines = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                for paragraph in shape.text_frame.paragraphs:
                    line = paragraph.text.strip()
                    if line:
                        slide_lines.append(line)
            elif shape.has_table:
                for row in shape.table.rows:
                    row_vals = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                    if row_vals:
                        slide_lines.append(" | ".join(row_vals))

        if slide_lines:
            text_parts.append(f"--- Slide {slide_idx} ---\n" + "\n".join(slide_lines))

    return "\n\n".join(text_parts)

def extract_text_from_ppt(file_path: str) -> str:
    """Fallback text extraction for legacy binary PPT files."""
    try:
        # Try pptx first in case it's actually an XML presentation misnamed as .ppt
        return extract_text_from_pptx(file_path)
    except Exception:
        pass

    # Binary string extraction fallback for legacy .ppt
    text_parts = []
    try:
        with open(file_path, "rb") as f:
            raw = f.read()
        # Extract ASCII / printable unicode sequences of length >= 4
        printable = re.findall(rb"[\x20-\x7E]{4,}", raw)
        filtered = [s.decode("latin1", errors="ignore").strip() for s in printable]
        # Filter out common binary noise
        meaningful = [s for s in filtered if len(s) > 5 and not s.startswith("Microsoft")]
        if meaningful:
            text_parts.append("\n".join(meaningful[:500]))
    except Exception as e:
        logger.warning(f"Fallback PPT extraction failed: {e}")

    return "\n\n".join(text_parts)

def clean_extracted_text(text: str) -> str:
    """
    Advanced conservative cleaner for OCR and extracted document text.
    - Normalizes non-printable characters and linebreaks.
    - Fixes broken line wraps while preserving headings, bullet points, numbered lists, tables, and code blocks.
    - Conservative de-hyphenation across line breaks (e.g. instruc-\\ntion -> instruction).
    - Removes isolated standalone page numbers and repeated running headers/footers across pages.
    - Conservative OCR repair (e.g. 'sou r ce' -> 'source', '1/0 port' -> 'I/O port', 'AK' -> 'AX' in register context).
    - Preserves all valid assembly mnemonics, formulas, and technical tokens without modification.
    """
    if not text:
        return ""

    # 1. Normalize line endings and non-printable control characters
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", " ", text)

    # 2. Conservative OCR de-hyphenation across line breaks
    # Handles: instruc-\ntion -> instruction, ad-\ndressing -> addressing
    # Preserves technical hyphens when followed by uppercase or digits (e.g. 8086-based)
    text = re.sub(r"(\b[A-Za-z]{2,})-\s*\n\s*([a-z]{2,}\b)", r"\1\2", text)

    # 3. Suppress standalone page numbers (e.g. 'Page 1', '1', '12 of 45')
    text = re.sub(r"(?m)^\s*(?:page|pg\.?)?\s*\d+(?:\s*(?:of|/)\s*\d+)?\s*$\n?", "", text, flags=re.IGNORECASE)

    # 4. Conservative OCR symbol, split-word & hardware repair
    text = re.sub(r"\bsou\s*r\s*ce\b", "source", text, flags=re.IGNORECASE)
    text = re.sub(r"\bdes\s*ti\s*na\s*tion\b", "destination", text, flags=re.IGNORECASE)
    text = re.sub(r"\b1/0\s*(?=port|read|write|address|bus|device)", "I/O ", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(AL|AX|register)(\s*(?:or|,)\s*)AK\b", r"\1\2AX", text)
    text = re.sub(r"\bAK(\s*(?:or|,)\s*)(AL|AX)\b", r"AX\1\2", text)
    text = re.sub(r"\bcontents\s+Of\s+the\b", "contents of the", text)
    text = re.sub(r"\bbits\s+Of\s+the\b", "bits of the", text)
    text = re.sub(r"\bstate\s+Of\s+the\b", "state of the", text)
    text = re.sub(r"\baddress\s+Of\s+the\b", "address of the", text)
    text = re.sub(r"\baddition\s+Of\s+two\b", "addition of two", text)
    text = re.sub(r"\bsubtraction\s+Of\s+two\b", "subtraction of two", text)

    # Known technical mnemonics that must never be altered or joined as lower-case sentences
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

    # 5. Suppress repeated running headers/footers across 3+ pages
    pages = re.split(r"(?m)^(--- (?:Page|Slide)\s+\d+\s+---)", text)
    if len(pages) > 3:
        header_candidates = {}
        for idx in range(2, len(pages), 2):
            p_lines = [l.strip() for l in pages[idx].split("\n") if l.strip()]
            if p_lines:
                first_line = p_lines[0]
                if 5 < len(first_line) < 80 and not first_line.startswith(("#", "-", "*", "|")):
                    header_candidates[first_line] = header_candidates.get(first_line, 0) + 1

        repeated_headers = {h for h, count in header_candidates.items() if count >= 3}
        if repeated_headers:
            for idx in range(2, len(pages), 2):
                p_lines = pages[idx].split("\n")
                p_filtered = [l for l in p_lines if l.strip() not in repeated_headers]
                pages[idx] = "\n".join(p_filtered)
        text = "".join(pages)

    # 6. Flow broken paragraph lines while preserving headings, lists, tables, code
    common_sentence_verbs = {
        "moves", "decrements", "increments", "copies", "exchanges", "transfers",
        "translates", "calculates", "loads", "stores", "performs", "rotates",
        "shifts", "adds", "subtracts", "adjusts", "prepares", "converts", "inverts", "repeats"
    }

    def is_heading_or_structural(l: str) -> bool:
        s = l.strip()
        if not s:
            return False
        if s.startswith("--- Page ") or s.startswith("--- Slide "):
            return True
        if s.startswith(("#", "-", "*", "•", "|", "+", ">")):
            return True
        if re.match(r"^\d+[\.\)]\s+", s) or re.match(r"^[a-zA-Z]\)\s+", s) or re.match(r"^\([iIvVxX\d]+\)\s+", s):
            return True
        if re.match(r"^(?:UNIT|CHAPTER|SECTION|PART|WEEK|AIM|EXPERIMENT|MODULE|TOPIC)\b", s, re.IGNORECASE):
            return True
        if s in ("Instruction", "Description/Working", "Description", "Syntax", "Example", "Flag Condition", "Opcode", "Operands"):
            return True
        if s.upper() in mnemonics:
            return True
        first_token = s.split()[0].upper() if s.split() else ""
        if first_token in mnemonics:
            return True
        if re.match(r"^[A-Za-z_]\w*:\s*(?:$|[A-Za-z]+)", s):
            return True
        if len(s) <= 65 and not re.search(r"[\.\!\?\,]\s*$", s):
            words = s.split()
            if 1 <= len(words) <= 8:
                if words[0].lower() in common_sentence_verbs:
                    return False
                if s.isupper() and len(s) > 3:
                    return True
                if s.endswith(":"):
                    return True
                cap_words = sum(1 for w in words if w[0].isupper() or w[0].isdigit())
                if cap_words / len(words) >= 0.75 and len(words) <= 6:
                    return True
        return False

    lines = text.split("\n")
    processed_lines = []

    i = 0
    while i < len(lines):
        line = lines[i]
        s_line = line.strip()

        if not s_line:
            processed_lines.append("")
            i += 1
            continue

        if is_heading_or_structural(line):
            if s_line.upper() in mnemonics:
                processed_lines.append(s_line.upper())
            else:
                processed_lines.append(s_line)
            i += 1
            continue

        para_parts = [s_line]
        while i + 1 < len(lines):
            next_line = lines[i + 1]
            s_next = next_line.strip()
            if not s_next or is_heading_or_structural(next_line):
                break
            if re.search(r"[\.\!\?]\s*$", para_parts[-1]) and re.match(r"^[A-Z]", s_next):
                break
            para_parts.append(s_next)
            i += 1

        processed_lines.append(" ".join(para_parts))
        i += 1

    cleaned = "\n".join(processed_lines)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned


def extract_text_from_file(file_path: str, file_type: Optional[str] = None) -> Dict[str, Any]:
    """
    Unified text extractor for PDF, DOCX, PPT, and PPTX study materials.
    Returns a dict with extraction status, cleaned text, and document metadata.
    """
    if not os.path.exists(file_path):
        return {
            "status": "error",
            "message": f"File not found: {file_path}",
            "text": ""
        }

    if os.path.getsize(file_path) == 0:
        return {
            "status": "error",
            "message": "The uploaded document is empty (0 bytes). Please upload a valid document.",
            "text": ""
        }

    ext = (file_type or os.path.splitext(file_path)[1].lstrip(".")).lower()
    extracted_text = ""

    try:
        if ext == "pdf":
            extracted_text = extract_text_from_pdf(file_path)
        elif ext in ("docx", "doc"):
            extracted_text = extract_text_from_docx(file_path)
        elif ext == "pptx":
            extracted_text = extract_text_from_pptx(file_path)
        elif ext == "ppt":
            extracted_text = extract_text_from_ppt(file_path)
        else:
            return {
                "status": "error",
                "message": f"Unsupported file extension: .{ext}. Supported formats: PDF, DOCX, PPT, PPTX.",
                "text": ""
            }

        cleaned = clean_extracted_text(extracted_text)

        if not cleaned or len(cleaned) < 20:
            return {
                "status": "error",
                "message": "The uploaded document contains no readable text. Please upload a clearer document.",
                "text": ""
            }

        words = cleaned.split()
        return {
            "status": "success",
            "file_path": file_path,
            "file_type": ext,
            "text": cleaned,
            "char_count": len(cleaned),
            "word_count": len(words)
        }

    except Exception as e:
        logger.error(f"Text extraction failed for {file_path}: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"Failed to extract text from document: {str(e)}",
            "text": ""
        }
