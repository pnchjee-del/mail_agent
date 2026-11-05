"""
Comprehensive File & Binary Reader for AI Mail Agent.
Supports .txt, .docx, .xlsx, .pdf, .png, .gif, and arbitrary binary files.
Extracts text, metadata, tabular data, visual summaries, hex dumps, and printable strings.
"""

import os
import io
import re
import csv
import math
import json
import base64
import hashlib
import zipfile
import tarfile
import sqlite3
from typing import Optional, Dict, Any, List, Tuple


def human_size(size_bytes: int) -> str:
    """Converts a byte count into a readable string (e.g. 1.2 MB)."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    for unit in ['KB', 'MB', 'GB', 'TB']:
        size_bytes /= 1024.0
        if size_bytes < 1024.0 or unit == 'TB':
            return f"{size_bytes:.1f} {unit}"
    return f"{size_bytes:.1f} TB"


def compute_hashes_and_entropy(data: bytes) -> Dict[str, Any]:
    """Calculates MD5, SHA-256 hashes, and Shannon entropy for binary inspection."""
    md5 = hashlib.md5(data).hexdigest()
    sha256 = hashlib.sha256(data).hexdigest()

    # Shannon Entropy in bits per byte (0.0 to 8.0)
    entropy = 0.0
    if len(data) > 0:
        byte_counts = [0] * 256
        for b in data:
            byte_counts[b] += 1
        total = len(data)
        for count in byte_counts:
            if count > 0:
                p = count / total
                entropy -= p * math.log2(p)

    # Classify entropy
    if entropy < 3.0:
        entropy_type = "Low (sparse/repetitive or empty data)"
    elif entropy < 6.8:
        entropy_type = "Moderate (text, code, or structured binary)"
    else:
        entropy_type = "High (compressed, packed, or encrypted data)"

    return {
        "md5": md5,
        "sha256": sha256,
        "entropy": round(entropy, 2),
        "entropy_type": entropy_type
    }


def generate_hexdump(data: bytes, max_bytes: int = 256) -> str:
    """Generates standard canonical hex dump of the first max_bytes bytes."""
    lines = []
    chunk = data[:max_bytes]
    for i in range(0, len(chunk), 16):
        block = chunk[i:i + 16]
        hex_parts = [f"{b:02x}" for b in block]
        hex_col1 = " ".join(hex_parts[:8])
        hex_col2 = " ".join(hex_parts[8:])
        hex_str = f"{hex_col1:<23}  {hex_col2:<23}".rstrip()
        ascii_chars = "".join(chr(b) if 32 <= b <= 126 else "." for b in block)
        lines.append(f"{i:08x}  {hex_str:<48}  |{ascii_chars}|")
    if len(data) > max_bytes:
        lines.append(f"... ({len(data) - max_bytes} more bytes)")
    return "\n".join(lines)


def extract_printable_strings(data: bytes, min_len: int = 4, max_strings: int = 50) -> List[str]:
    """Extracts printable ASCII sequences of at least min_len characters (like strings tool)."""
    pattern = re.compile(rb'[A-Za-z0-9/\-_. :@#!=+()\[\]{}~,;?%]{' + str(min_len).encode() + rb',}')
    matches = pattern.findall(data)
    results = []
    for m in matches[:max_strings * 2]:
        s = m.decode('ascii', errors='ignore').strip()
        if len(s) >= min_len and s not in results:
            results.append(s)
        if len(results) >= max_strings:
            break
    return results


def detect_magic_type(data: bytes, filename: str = "") -> Tuple[str, str]:
    """Identifies the file type and MIME type from magic header bytes."""
    ext = os.path.splitext(filename)[1].lower().lstrip('.')
    
    if data.startswith(b'%PDF-'):
        return "PDF Document", "application/pdf"
    if data.startswith(b'\x89PNG\r\n\x1a\n'):
        return "PNG Image", "image/png"
    if data.startswith(b'GIF87a') or data.startswith(b'GIF89a'):
        return "GIF Image", "image/gif"
    if data.startswith(b'\xff\xd8\xff'):
        return "JPEG Image", "image/jpeg"
    if data.startswith(b'RIFF') and b'WEBP' in data[:16]:
        return "WebP Image", "image/webp"
    if data.startswith(b'BM'):
        return "BMP Image", "image/bmp"
    if data.startswith(b'PK\x03\x04'):
        # Could be docx, xlsx, pptx, or zip
        if ext == 'docx':
            return "Word Document", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        if ext == 'xlsx':
            return "Excel Spreadsheet", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        if ext == 'pptx':
            return "PowerPoint Presentation", "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        return "ZIP Archive", "application/zip"
    if data.startswith(b'7z\xbc\xaf\x27\x1c'):
        return "7-Zip Archive", "application/x-7z-compressed"
    if data.startswith(b'Rar!\x1a\x07'):
        return "RAR Archive", "application/x-rar-compressed"
    if data.startswith(b'\x1f\x8b\x08'):
        return "GZIP Compressed File", "application/gzip"
    if data.startswith(b'SQLite format 3\x00'):
        return "SQLite Database", "application/x-sqlite3"
    if data.startswith(b'MZ'):
        return "Windows Executable / DLL", "application/x-msdownload"
    if data.startswith(b'\x7fELF'):
        return "Linux ELF Executable", "application/x-executable"
    if data.startswith(b'\xca\xfe\xba\xbe'):
        return "Java Class / Mach-O Binary", "application/java-vm"
    if data.startswith(b'ID3') or (len(data) > 1 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0):
        return "MP3 Audio", "audio/mpeg"
    if data.startswith(b'RIFF') and b'WAVE' in data[:16]:
        return "WAV Audio", "audio/wav"
    if len(data) >= 12 and data[4:8] == b'ftyp':
        return "MP4 Video", "video/mp4"

    # Known extensions if magic didn't trigger
    ext_map = {
        "txt": ("Plain Text", "text/plain"),
        "csv": ("CSV Spreadsheet", "text/csv"),
        "tsv": ("TSV Tabular Data", "text/tab-separated-values"),
        "json": ("JSON Data", "application/json"),
        "xml": ("XML Document", "application/xml"),
        "html": ("HTML Document", "text/html"),
        "htm": ("HTML Document", "text/html"),
        "md": ("Markdown Document", "text/markdown"),
        "log": ("Log File", "text/plain"),
        "yaml": ("YAML Configuration", "text/yaml"),
        "yml": ("YAML Configuration", "text/yaml"),
        "docx": ("Word Document", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        "doc": ("Legacy Word Document", "application/msword"),
        "xlsx": ("Excel Spreadsheet", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        "xls": ("Legacy Excel Spreadsheet", "application/vnd.ms-excel"),
        "pdf": ("PDF Document", "application/pdf"),
        "png": ("PNG Image", "image/png"),
        "gif": ("GIF Image", "image/gif"),
        "jpg": ("JPEG Image", "image/jpeg"),
        "jpeg": ("JPEG Image", "image/jpeg"),
        "webp": ("WebP Image", "image/webp"),
        "zip": ("ZIP Archive", "application/zip"),
        "tar": ("TAR Archive", "application/x-tar"),
        "db": ("Database File", "application/octet-stream"),
        "sqlite": ("SQLite Database", "application/x-sqlite3")
    }

    if ext in ext_map:
        return ext_map[ext]

    # Check if mostly text
    sample = data[:1024]
    try:
        sample.decode('utf-8')
        return "Plain Text", "text/plain"
    except UnicodeDecodeError:
        return "Binary File", "application/octet-stream"


class FileReader:
    """Master multi-format file reader for AI agents."""

    def __init__(self, openai_client=None):
        self.openai_client = openai_client

    def set_openai_client(self, client):
        self.openai_client = client

    def read_file(self, file_path: str, max_text_chars: int = 15000) -> Dict[str, Any]:
        """Reads a file from a local disk path."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        with open(file_path, "rb") as f:
            data = f.read()
        filename = os.path.basename(file_path)
        return self.read_bytes(data, filename=filename, max_text_chars=max_text_chars)

    def read_bytes(self, data: bytes, filename: str = "unknown.bin", max_text_chars: int = 15000) -> Dict[str, Any]:
        """Reads and analyzes raw file bytes based on file format."""
        size = len(data)
        ext = os.path.splitext(filename)[1].lower().lstrip('.')
        file_type, mime_type = detect_magic_type(data, filename=filename)
        hashes_info = compute_hashes_and_entropy(data)

        base_res: Dict[str, Any] = {
            "filename": filename,
            "extension": ext or "bin",
            "file_type": file_type,
            "mime_type": mime_type,
            "size_bytes": size,
            "size_human": human_size(size),
            "is_binary": True,
            "metadata": hashes_info,
            "text_content": "",
            "summary": "",
            "key_points": [],
            "tables": [],
            "preview_snippet": "",
            "error": None
        }

        try:
            # 1. CSV / TSV tabular files
            if ext in ["csv", "tsv"] or mime_type in ["text/csv", "text/tab-separated-values"]:
                return self._parse_csv_tsv(data, base_res, max_text_chars)

            # 2. Plain text and text formats
            if ext in ["txt", "log", "md", "json", "xml", "html", "htm", "yaml", "yml", "ini", "cfg", "py", "js", "css", "sql"] or mime_type.startswith("text/"):
                return self._parse_text(data, base_res, max_text_chars)

            # 3. Microsoft Word (.docx)
            if ext == "docx" or file_type == "Word Document":
                return self._parse_docx(data, base_res, max_text_chars)

            # 4. Microsoft Excel (.xlsx)
            if ext == "xlsx" or file_type == "Excel Spreadsheet":
                return self._parse_xlsx(data, base_res, max_text_chars)

            # 5. PDF documents (.pdf)
            if ext == "pdf" or file_type == "PDF Document":
                return self._parse_pdf(data, base_res, max_text_chars)

            # 6. Animated GIF images (.gif)
            if ext == "gif" or file_type == "GIF Image":
                return self._parse_gif(data, base_res)

            # 7. Other images (.png, .jpg, .jpeg, .webp, .bmp)
            if ext in ["png", "jpg", "jpeg", "webp", "bmp", "tiff"] or mime_type.startswith("image/"):
                return self._parse_image(data, base_res)

            # 8. Archive formats (.zip, .tar, .gz)
            if ext in ["zip", "tar", "gz"] or file_type in ["ZIP Archive", "7-Zip Archive"]:
                return self._parse_archive(data, base_res)

            # 9. SQLite Database
            if ext in ["db", "sqlite", "sqlite3"] or file_type == "SQLite Database":
                return self._parse_sqlite(data, base_res)

            # 10. General Binary Fallback (exe, dat, bin, etc.)
            return self._parse_generic_binary(data, base_res)

        except Exception as e:
            base_res["error"] = f"Extraction error: {str(e)}"
            return self._parse_generic_binary(data, base_res)

    # -------------------------------------------------------------
    # Document Summarization Engine (AI LLM + Extractive NLP Fallback)
    # -------------------------------------------------------------

    def summarize_document(self, text: str, tables: list = None, filename: str = "", file_type: str = "") -> Tuple[str, List[str]]:
        """Summarizes document content using an active LLM if available and functional,
        otherwise seamlessly falls back to the intelligent NLP extractive summarizer.
        Returns: (summary_str, key_points_list)
        """
        if not text or not text.strip():
            fn_str = f"'{filename}'" if filename else file_type
            return f"{fn_str} contains no readable text or is image/scanned-only.", []

        # 1. Attempt LLM summarization if client is available
        if self.openai_client:
            try:
                prompt = f"""You are an expert executive document analyst. Given the text extracted from '{filename}' ({file_type}), provide an accurate, clear, 2-3 sentence executive summary.
Clearly identify:
1. What the document is (e.g., Driving Licence Renewal Application, Tax Invoice, Services Agreement, Quarterly Report).
2. Key subjects, entities/parties, important dates, and amounts.
3. Any required action or conclusion.

Respond in strictly valid JSON format with this exact schema (no markdown, no backticks):
{{
  "summary": "2-3 concise, informative sentences summarizing the core document contents.",
  "key_points": [
    "Key highlight or section 1",
    "Key highlight or section 2",
    "Key highlight or section 3"
  ]
}}

Document Content Preview:
{text[:4500]}
"""
                resp = self.openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1,
                    max_tokens=300,
                    timeout=8.0
                )
                raw_out = resp.choices[0].message.content.strip()
                if raw_out.startswith("```"):
                    raw_out = re.sub(r"^```(?:json)?\s*", "", raw_out)
                    raw_out = re.sub(r"\s*```$", "", raw_out)
                parsed = json.loads(raw_out)
                llm_summary = parsed.get("summary", "").strip()
                llm_points = parsed.get("key_points", [])
                if llm_summary:
                    return llm_summary, llm_points
            except Exception as e:
                # Silently proceed to high-precision extractive fallback
                pass

        # 2. Intelligent Extractive NLP Fallback (100% reliable offline / quota-exceeded)
        return self.generate_extractive_summary(text, tables=tables, filename=filename, file_type=file_type)

    def generate_extractive_summary(self, text: str, tables: list = None, filename: str = "", file_type: str = "") -> Tuple[str, List[str]]:
        """High-precision heuristic & pattern-matching summarizer for documents and tabular data."""
        lines = [line.strip() for line in text.splitlines() if line.strip() and not line.startswith("--- Page")]
        clean_text = " ".join(lines)
        lower_text = clean_text.lower()

        # Classify document nature
        doc_type = "Document"
        if any(k in lower_text for k in ["application for", "licence", "license", "form 1", "form 2", "form 3", "form 4", "registration form", "enrollment", "rto", "sarathi"]):
            doc_type = "Official Application / Form"
        elif any(k in lower_text for k in ["invoice", "receipt", "bill to", "tax invoice", "statement of account", "pension slip", "financials", "cogs", "budget", "balance"]):
            doc_type = "Financial / Billing Document"
        elif any(k in lower_text for k in ["agreement", "contract", "terms of service", "non-disclosure", "services agreement", "memorandum"]):
            doc_type = "Legal Agreement / Contract"
        elif any(k in lower_text for k in ["minutes", "meeting notes", "board of directors", "attendees", "action items"]):
            doc_type = "Meeting Record"
        elif any(k in lower_text for k in ["resume", "curriculum vitae", "work experience", "education"]):
            doc_type = "Resume / CV"
        elif any(k in lower_text for k in ["report", "quarterly", "annual", "policy", "audit", "investigation"]):
            doc_type = "Report / Policy Document"

        # Identify primary title or main topic from the first 20 lines
        title = ""
        for line in lines[:20]:
            clean_l = re.sub(r'^[\[\(\d\.\-\*#\]\s]+', '', line).strip()
            clean_l = re.sub(r'\[See rules[^\]]*\]', '', clean_l).strip()
            if len(clean_l) > 6 and not re.match(r'^(page|\d+|see rule|rules|to,|date:|services applying)', clean_l, re.IGNORECASE):
                if not title or len(clean_l) > len(title):
                    title = clean_l
                    if len(title) > 60:
                        break
        if not title:
            title = os.path.splitext(filename)[0] if filename else file_type

        # Extract key sections / structural items
        key_points = []
        key_points.append(f"Purpose: {title[:110]}")

        section_patterns = [
            r'(?:form of application for [^\n\r.]+)',
            r'(?:services applying for [^\n\r.]+)',
            r'(?:personal details [^\n\r.]+)',
            r'(?:class of vehicles? [^\n\r.]+)',
            r'(?:annexure[^\n\r.]*)',
            r'(?:list of documents [^\n\r.]+)',
            r'(?:deliverable:[^\n\r.]+)',
            r'(?:client:[^\n\r.]+)',
            r'(?:status:[^\n\r.]+)',
            r'(?:department:[^\n\r.]+)',
            r'(?:terms and conditions[^\n\r.]*)',
            r'(?:action items?[^\n\r.]*)'
        ]
        found_sections = []
        for pat in section_patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                s_clean = re.sub(r'\s+', ' ', m.group(0)).strip()
                s_clean = re.sub(r'^[\[\(\d\.\-\*#\]\s]+', '', s_clean)
                if s_clean and len(s_clean) > 5 and s_clean.title() not in [x.title() for x in found_sections]:
                    found_sections.append(s_clean)
                    if len(found_sections) >= 3:
                        break

        if found_sections:
            key_points.append("Key Sections: " + "; ".join(found_sections[:3]))

        # Extract dates & monetary amounts
        dates = re.findall(r'\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{2,4})\b', text, re.IGNORECASE)
        amounts = re.findall(r'\b(?:[\$€£₹]|(?:Rs\.?|USD|EUR)[ \t]*)\d[\d,]*(?:\.\d{1,2})?\b', text, re.IGNORECASE)

        details_parts = []
        if amounts:
            details_parts.append(f"Amount: {', '.join(amounts[:2])}")
        if dates:
            details_parts.append(f"Date: {dates[0]}")
        if details_parts:
            key_points.append(", ".join(details_parts))

        if tables:
            tbl_names = [t.get("name", "Table") for t in tables if isinstance(t, dict)]
            if tbl_names:
                key_points.append(f"Data Tables: {', '.join(tbl_names[:3])}")

        # Build clean lead sentences
        lead_sentences = []
        for line in lines[:25]:
            clean_l = re.sub(r'^[\[\(\d\.\-\*#\]\s]+', '', line).strip()
            clean_l = re.sub(r'\[?See rules[^\]]*\]?', '', clean_l, flags=re.IGNORECASE).strip()
            clean_l = clean_l.lstrip('.,:; \t\r\n')
            if len(clean_l) > 15 and not clean_l.startswith("---") and not clean_l.lower().startswith("form 2"):
                lead_sentences.append(clean_l)
                if len(lead_sentences) >= 2:
                    break

        lead_text = ". ".join(lead_sentences) if lead_sentences else title
        if len(lead_text) > 160:
            lead_text = lead_text[:157] + "..."

        fn_display = f"'{filename}'" if filename else file_type
        summary = f"{doc_type} {fn_display}: {lead_text}."
        if found_sections:
            summary += f" Details include {', '.join(found_sections[:2])}."

        return summary, key_points

    # -------------------------------------------------------------
    # Parsers
    # -------------------------------------------------------------

    def _parse_text(self, data: bytes, res: Dict[str, Any], max_chars: int) -> Dict[str, Any]:
        res["is_binary"] = False
        text = ""
        for enc in ['utf-8', 'utf-16', 'cp1252', 'latin-1']:
            try:
                text = data.decode(enc)
                res["metadata"]["encoding"] = enc
                break
            except UnicodeDecodeError:
                continue
        if not text:
            text = data.decode('utf-8', errors='replace')
            res["metadata"]["encoding"] = "utf-8 (with replacement)"

        lines = text.splitlines()
        res["metadata"]["line_count"] = len(lines)
        res["metadata"]["char_count"] = len(text)
        res["metadata"]["word_count"] = len(text.split())

        res["text_content"] = text[:max_chars]
        res["preview_snippet"] = text[:300].strip()
        summary, key_points = self.summarize_document(text, filename=res["filename"], file_type="Plain Text")
        res["summary"] = summary
        res["key_points"] = key_points
        return res

    def _parse_csv_tsv(self, data: bytes, res: Dict[str, Any], max_chars: int) -> Dict[str, Any]:
        res["is_binary"] = False
        text = ""
        for enc in ['utf-8', 'cp1252', 'latin-1']:
            try:
                text = data.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        if not text:
            text = data.decode('utf-8', errors='replace')

        delimiter = '\t' if res["extension"] == 'tsv' else ','
        # Attempt sniffing if comma/tab ambiguous
        try:
            sniffer = csv.Sniffer()
            dialect = sniffer.sniff(text[:2048])
            delimiter = dialect.delimiter
        except Exception:
            pass

        reader = csv.reader(io.StringIO(text), delimiter=delimiter)
        rows = list(reader)
        row_count = len(rows)
        col_count = len(rows[0]) if rows else 0

        res["metadata"]["rows"] = row_count
        res["metadata"]["columns"] = col_count
        res["metadata"]["headers"] = rows[0] if rows else []

        # Render clean markdown table for preview (up to 30 rows)
        preview_rows = rows[:30]
        md_table = []
        if preview_rows:
            header = preview_rows[0]
            md_table.append("| " + " | ".join(str(c) for c in header) + " |")
            md_table.append("| " + " | ".join(["---"] * len(header)) + " |")
            for r in preview_rows[1:]:
                # Pad or slice to match header
                padded = list(r) + [""] * (len(header) - len(r))
                md_table.append("| " + " | ".join(str(c).replace("\n", " ") for c in padded[:len(header)]) + " |")

        table_text = "\n".join(md_table)
        res["tables"] = [{"name": "CSV Data", "rows": row_count, "columns": col_count, "markdown": table_text}]
        res["text_content"] = f"### CSV Data ({row_count} rows, {col_count} columns)\n\n" + table_text[:max_chars]
        res["preview_snippet"] = f"{row_count} rows, columns: {', '.join(rows[0][:6]) if rows else 'None'}"
        summary, key_points = self.summarize_document(table_text, tables=res["tables"], filename=res["filename"], file_type="CSV Spreadsheet")
        res["summary"] = summary
        res["key_points"] = key_points
        return res

    def _parse_docx(self, data: bytes, res: Dict[str, Any], max_chars: int) -> Dict[str, Any]:
        res["is_binary"] = False
        import docx
        doc = docx.Document(io.BytesIO(data))

        # Extract Core Properties
        props = doc.core_properties
        res["metadata"]["author"] = props.author or "Unknown"
        res["metadata"]["title"] = props.title or ""
        res["metadata"]["created"] = str(props.created) if props.created else ""
        res["metadata"]["modified"] = str(props.modified) if props.modified else ""

        extracted_parts = []
        if props.title:
            extracted_parts.append(f"# {props.title}\n")

        # Paragraphs & Headings
        para_count = 0
        for p in doc.paragraphs:
            text = p.text.strip()
            if text:
                para_count += 1
                if p.style and 'Heading 1' in p.style.name:
                    extracted_parts.append(f"\n# {text}\n")
                elif p.style and 'Heading 2' in p.style.name:
                    extracted_parts.append(f"\n## {text}\n")
                elif p.style and 'Heading 3' in p.style.name:
                    extracted_parts.append(f"\n### {text}\n")
                else:
                    extracted_parts.append(text)

        # Tables
        tables_data = []
        for t_idx, table in enumerate(doc.tables, 1):
            t_rows = []
            for row in table.rows:
                row_cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
                # Avoid adjacent duplicate cells from merged rows
                deduped = []
                for cell in row_cells:
                    if not deduped or deduped[-1] != cell:
                        deduped.append(cell)
                t_rows.append(deduped)

            if t_rows:
                md_t = []
                header = t_rows[0]
                md_t.append("| " + " | ".join(header) + " |")
                md_t.append("| " + " | ".join(["---"] * len(header)) + " |")
                for r in t_rows[1:]:
                    padded = list(r) + [""] * (len(header) - len(r))
                    md_t.append("| " + " | ".join(padded[:len(header)]) + " |")
                tbl_md = "\n".join(md_t)
                tables_data.append({"name": f"Table {t_idx}", "markdown": tbl_md})
                extracted_parts.append(f"\n\n**[Table {t_idx}]**\n" + tbl_md + "\n")

        full_text = "\n\n".join(extracted_parts)
        res["tables"] = tables_data
        res["metadata"]["paragraph_count"] = para_count
        res["metadata"]["table_count"] = len(doc.tables)
        res["metadata"]["word_count"] = len(full_text.split())
        res["text_content"] = full_text[:max_chars]
        res["preview_snippet"] = full_text[:300].strip()
        summary, key_points = self.summarize_document(full_text, tables=tables_data, filename=res["filename"], file_type="Word Document")
        res["summary"] = summary
        res["key_points"] = key_points
        return res

    def _parse_xlsx(self, data: bytes, res: Dict[str, Any], max_chars: int) -> Dict[str, Any]:
        res["is_binary"] = False
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(data), data_only=True, read_only=True)

        sheet_names = wb.sheetnames
        res["metadata"]["sheets"] = sheet_names
        res["metadata"]["sheet_count"] = len(sheet_names)

        all_text = []
        tables_list = []

        for name in sheet_names[:5]:  # Process up to first 5 sheets
            ws = wb[name]
            rows = []
            # Read first 35 rows per sheet
            for r_idx, row in enumerate(ws.iter_rows(values_only=True), 1):
                if r_idx > 35:
                    break
                # Filter out trailing None values
                row_vals = [str(val).strip() if val is not None else "" for val in row]
                if any(row_vals):
                    rows.append(row_vals)

            if rows:
                header = rows[0]
                md_lines = [f"#### Sheet: {name} ({len(rows)} preview rows, {len(header)} cols)"]
                md_lines.append("| " + " | ".join(header) + " |")
                md_lines.append("| " + " | ".join(["---"] * len(header)) + " |")
                for r in rows[1:]:
                    padded = list(r) + [""] * (len(header) - len(r))
                    md_lines.append("| " + " | ".join(padded[:len(header)]) + " |")
                tbl_md = "\n".join(md_lines)
                tables_list.append({"name": name, "markdown": tbl_md})
                all_text.append(tbl_md)

        wb.close()
        combined = "\n\n".join(all_text)
        res["tables"] = tables_list
        res["text_content"] = combined[:max_chars]
        res["preview_snippet"] = f"Excel Workbook ({len(sheet_names)} sheets: {', '.join(sheet_names[:4])})"
        summary, key_points = self.summarize_document(combined, tables=tables_list, filename=res["filename"], file_type="Excel Spreadsheet")
        res["summary"] = summary
        res["key_points"] = key_points
        return res

    def _parse_pdf(self, data: bytes, res: Dict[str, Any], max_chars: int) -> Dict[str, Any]:
        res["is_binary"] = False
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(data))

        page_count = len(reader.pages)
        res["metadata"]["page_count"] = page_count

        meta = reader.metadata or {}
        res["metadata"]["title"] = meta.get('/Title', '')
        res["metadata"]["author"] = meta.get('/Author', '')
        res["metadata"]["subject"] = meta.get('/Subject', '')
        res["metadata"]["creator"] = meta.get('/Creator', '')

        pages_text = []
        total_extracted_len = 0
        for p_idx, page in enumerate(reader.pages, 1):
            p_text = page.extract_text() or ""
            p_clean = p_text.strip()
            total_extracted_len += len(p_clean)
            pages_text.append(f"--- Page {p_idx} ---\n{p_clean}")
            if total_extracted_len > max_chars:
                pages_text.append(f"\n[Truncated remaining pages after Page {p_idx}]")
                break

        full_text = "\n\n".join(pages_text)
        if total_extracted_len < 40 and page_count > 0:
            full_text += "\n\n*(Note: This PDF appears to be scanned or contains image-only pages without selectable text layer.)*"
            res["metadata"]["is_scanned"] = True
        else:
            res["metadata"]["is_scanned"] = False

        res["metadata"]["word_count"] = len(full_text.split())
        res["text_content"] = full_text[:max_chars]
        res["preview_snippet"] = full_text[:300].strip()
        summary, key_points = self.summarize_document(full_text, filename=res["filename"], file_type="PDF Document")
        res["summary"] = summary
        res["key_points"] = key_points
        return res

    def _parse_image(self, data: bytes, res: Dict[str, Any]) -> Dict[str, Any]:
        from PIL import Image
        img = Image.open(io.BytesIO(data))

        width, height = img.size
        res["metadata"]["dimensions"] = f"{width} x {height}"
        res["metadata"]["width"] = width
        res["metadata"]["height"] = height
        res["metadata"]["format"] = img.format or "Image"
        res["metadata"]["mode"] = img.mode

        # AI Vision Analysis if OpenAI Client is active
        vision_analysis = ""
        if self.openai_client:
            vision_analysis = self._describe_image_with_vision(data, mime_type=res["mime_type"])

        if vision_analysis and not vision_analysis.startswith("[AI Vision Analysis unavailable"):
            res["text_content"] = vision_analysis
            res["summary"] = f"Image ({width}x{height} {img.format}): {vision_analysis[:180]}..."
            res["preview_snippet"] = vision_analysis[:280]
        else:
            info_text = f"Image File: {img.format} ({width} x {height} px, Color Mode: {img.mode}, Size: {res['size_human']})."
            res["text_content"] = info_text
            res["summary"] = info_text
            res["preview_snippet"] = info_text

        return res

    def _parse_gif(self, data: bytes, res: Dict[str, Any]) -> Dict[str, Any]:
        from PIL import Image
        img = Image.open(io.BytesIO(data))

        width, height = img.size
        is_animated = getattr(img, "is_animated", False)
        n_frames = getattr(img, "n_frames", 1)

        durations = []
        try:
            for frame_idx in range(min(n_frames, 10)):
                img.seek(frame_idx)
                durations.append(img.info.get('duration', 100))
        except Exception:
            pass

        avg_duration = sum(durations) / len(durations) if durations else 100
        total_seconds = (avg_duration * n_frames) / 1000.0

        res["metadata"]["dimensions"] = f"{width} x {height}"
        res["metadata"]["is_animated"] = is_animated
        res["metadata"]["frame_count"] = n_frames
        res["metadata"]["estimated_duration"] = f"{total_seconds:.1f}s" if is_animated else "Static"

        # Vision on first frame if animated or static
        vision_analysis = ""
        if self.openai_client:
            # Extract first frame as PNG/JPEG
            img.seek(0)
            buf = io.BytesIO()
            img.convert('RGB').save(buf, format='JPEG', quality=85)
            frame_bytes = buf.getvalue()
            vision_analysis = self._describe_image_with_vision(frame_bytes, mime_type="image/jpeg", is_gif=True, n_frames=n_frames)

        desc = f"GIF Animation ({width}x{height}, {n_frames} frames, {total_seconds:.1f}s duration)" if is_animated else f"Static GIF Image ({width}x{height})"
        if vision_analysis and not vision_analysis.startswith("[AI Vision Analysis unavailable"):
            res["text_content"] = f"{desc}\n\n**Visual Analysis:**\n{vision_analysis}"
            res["summary"] = f"{desc}: {vision_analysis[:160]}..."
            res["preview_snippet"] = vision_analysis[:260]
        else:
            res["text_content"] = desc
            res["summary"] = desc
            res["preview_snippet"] = desc

        return res

    def _parse_archive(self, data: bytes, res: Dict[str, Any]) -> Dict[str, Any]:
        res["is_binary"] = True
        file_list = []
        total_uncompressed = 0

        # Try ZIP
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                for info in zf.infolist()[:80]:
                    file_list.append({
                        "name": info.filename,
                        "size": human_size(info.file_size),
                        "is_dir": info.is_dir()
                    })
                    total_uncompressed += info.file_size
                res["metadata"]["archive_type"] = "ZIP"
                res["metadata"]["file_count"] = len(zf.infolist())
                res["metadata"]["uncompressed_size"] = human_size(total_uncompressed)
        except Exception:
            # Try TAR
            try:
                with tarfile.open(fileobj=io.BytesIO(data)) as tf:
                    members = tf.getmembers()
                    for m in members[:80]:
                        file_list.append({
                            "name": m.name,
                            "size": human_size(m.size),
                            "is_dir": m.isdir()
                        })
                        total_uncompressed += m.size
                    res["metadata"]["archive_type"] = "TAR"
                    res["metadata"]["file_count"] = len(members)
                    res["metadata"]["uncompressed_size"] = human_size(total_uncompressed)
            except Exception:
                pass

        table_lines = ["| File Name | Size | Type |", "| --- | --- | --- |"]
        for f in file_list[:40]:
            ftype = "Folder" if f["is_dir"] else "File"
            table_lines.append(f"| {f['name']} | {f['size']} | {ftype} |")

        content = f"### Archive Contents ({len(file_list)} files, Total {human_size(total_uncompressed)})\n\n" + "\n".join(table_lines)
        res["text_content"] = content
        res["summary"] = f"Archive package containing {len(file_list)} files ({human_size(total_uncompressed)} uncompressed)."
        res["preview_snippet"] = f"{len(file_list)} files inside archive: {', '.join(f['name'] for f in file_list[:4])}"
        return res

    def _parse_sqlite(self, data: bytes, res: Dict[str, Any]) -> Dict[str, Any]:
        res["is_binary"] = True
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp:
            tmp.write(data)
            tmp_path = tmp.name

        try:
            conn = sqlite3.connect(tmp_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall() if not row[0].startswith("sqlite_")]
            res["metadata"]["tables"] = tables
            res["metadata"]["table_count"] = len(tables)

            out_tables = []
            for t in tables[:6]:
                cursor.execute(f"PRAGMA table_info('{t}')")
                cols = [c[1] for c in cursor.fetchall()]
                cursor.execute(f"SELECT COUNT(*) FROM '{t}'")
                cnt = cursor.fetchone()[0]
                cursor.execute(f"SELECT * FROM '{t}' LIMIT 10")
                sample_rows = cursor.fetchall()

                md_lines = [f"#### Table: {t} ({cnt} total rows)"]
                md_lines.append("| " + " | ".join(cols) + " |")
                md_lines.append("| " + " | ".join(["---"] * len(cols)) + " |")
                for r in sample_rows:
                    md_lines.append("| " + " | ".join(str(v).replace("\n", " ") for v in r) + " |")
                tbl_md = "\n".join(md_lines)
                out_tables.append(tbl_md)

            conn.close()
            combined = "\n\n".join(out_tables)
            res["text_content"] = combined
            res["summary"] = f"SQLite Database with {len(tables)} tables: {', '.join(tables)}."
            res["preview_snippet"] = f"Tables: {', '.join(tables)}"
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

        return res

    def _parse_generic_binary(self, data: bytes, res: Dict[str, Any]) -> Dict[str, Any]:
        """Provides structural metadata, hex dump, and printable strings for arbitrary binary files."""
        res["is_binary"] = True
        hexdump = generate_hexdump(data, max_bytes=256)
        strings_list = extract_printable_strings(data, min_len=4, max_strings=40)

        res["metadata"]["hexdump"] = hexdump
        res["metadata"]["printable_strings_count"] = len(strings_list)
        res["metadata"]["sample_strings"] = strings_list[:15]

        content_parts = [
            f"### Binary File Analysis: {res['filename']}",
            f"- **File Type:** {res['file_type']} ({res['mime_type']})",
            f"- **Size:** {res['size_human']} ({res['size_bytes']} bytes)",
            f"- **Entropy:** {res['metadata']['entropy']} / 8.0 — {res['metadata']['entropy_type']}",
            f"- **MD5:** `{res['metadata']['md5']}`",
            f"- **SHA-256:** `{res['metadata']['sha256']}`",
            "\n#### Hex Header Preview (First 256 bytes):",
            "```text\n" + hexdump + "\n```",
        ]

        if strings_list:
            content_parts.append("\n#### Embedded Printable Strings (Preview):")
            content_parts.append("```text\n" + "\n".join(strings_list[:35]) + "\n```")

        full_analysis = "\n".join(content_parts)
        res["text_content"] = full_analysis
        res["preview_snippet"] = f"Binary ({res['file_type']}, {res['size_human']}, entropy: {res['metadata']['entropy']})"
        res["summary"] = f"Binary file of type '{res['file_type']}' ({res['size_human']}), entropy {res['metadata']['entropy']}."
        return res

    def _describe_image_with_vision(self, image_bytes: bytes, mime_type: str = "image/png", is_gif: bool = False, n_frames: int = 1) -> str:
        """Uses OpenAI GPT-4o-mini Vision to analyze an image or key GIF frame."""
        if not self.openai_client:
            return ""

        try:
            # Re-encode to efficient JPEG if very large
            if len(image_bytes) > 2 * 1024 * 1024:
                from PIL import Image
                im = Image.open(io.BytesIO(image_bytes))
                im.thumbnail((1600, 1600))
                b_out = io.BytesIO()
                im.convert('RGB').save(b_out, format='JPEG', quality=80)
                image_bytes = b_out.getvalue()
                mime_type = "image/jpeg"

            b64_str = base64.b64encode(image_bytes).decode('utf-8')
            data_url = f"data:{mime_type};base64,{b64_str}"

            prompt = (
                "You are an AI document and image analyst. "
                "1. If this image contains text (receipt, document, slide, screenshot, code), extract and transcribe all visible text accurately. "
                "2. If it contains a chart, diagram, or table, describe the data, columns, and key numbers. "
                "3. Provide a clear, concise executive summary of what is shown."
            )
            if is_gif:
                prompt += f" Note: This is a representative frame from an animated GIF with {n_frames} frames."

            resp = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": data_url, "detail": "high"}}
                        ]
                    }
                ],
                max_tokens=600,
                temperature=0.1,
                timeout=8.0
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            return f"[AI Vision Analysis unavailable: {e}]"

    def format_for_llm(self, res: Dict[str, Any], max_chars: int = 4000) -> str:
        """Formats the file read result into a prompt-ready context block for the LLM."""
        fn = res.get("filename", "unknown")
        ftype = res.get("file_type", "Binary")
        size = res.get("size_human", "")
        summary = res.get("summary", "")
        kps = res.get("key_points", [])
        kp_str = ("\nKey Highlights:\n" + "\n".join(f"- {kp}" for kp in kps)) if kps else ""
        text = res.get("text_content", "")[:max_chars]

        return (
            f"[ATTACHED FILE: '{fn}' | Type: {ftype} | Size: {size}]\n"
            f"Summary: {summary}{kp_str}\n"
            f"Content:\n{text}\n"
            f"[END OF FILE: '{fn}']"
        )
