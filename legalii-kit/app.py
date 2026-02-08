from pathlib import Path
from datetime import datetime
from typing import Dict, Any
import json
import os
import io
import re
import hashlib
import hmac
import base64
import secrets

from fastapi import FastAPI, UploadFile, File, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse, Response
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent
RULES_PATH = ROOT / "config" / "06-ruleset-extranjeria-v1.json"
FIXTURES_DIR = ROOT / "fixtures"
UI_DIR = ROOT / "ui"

APP_ENV = os.getenv("LEGALII_ENV", "local").lower()
REQUIRE_AUTH = os.getenv("LEGALII_REQUIRE_AUTH", "false").lower() == "true"
API_KEY = os.getenv("LEGALII_API_KEY", "").strip()
AUDIT_LOG = Path(os.getenv("LEGALII_AUDIT_LOG", str(ROOT.parent / "enterprise" / "logs" / "audit.log")))
INGEST_DIR = Path(os.getenv("LEGALII_INGEST_DIR", str(ROOT.parent / "enterprise" / "data" / "ingest")))
STRICT_MODE = os.getenv("LEGALII_STRICT_MODE", "true").lower() == "true"
API_KEYS_JSON = os.getenv("LEGALII_API_KEYS_JSON", "").strip()
REVIEW_LOG = Path(os.getenv("LEGALII_REVIEW_LOG", str(ROOT.parent / "enterprise" / "logs" / "review.log")))
REVIEW_QUEUE = Path(os.getenv("LEGALII_REVIEW_QUEUE", str(ROOT.parent / "enterprise" / "data" / "review_queue.jsonl")))
CASES_DIR = Path(os.getenv("LEGALII_CASES_DIR", str(ROOT.parent / "enterprise" / "data" / "cases")))
USER_STORE = Path(os.getenv("LEGALII_USER_STORE", str(ROOT.parent / "enterprise" / "data" / "users.json")))
TOKEN_SECRET = os.getenv("LEGALII_TOKEN_SECRET", API_KEY or "legalii-dev-secret")
TOKEN_TTL_SECONDS = int(os.getenv("LEGALII_TOKEN_TTL_SECONDS", "28800"))

app = FastAPI(title="LEGALII Enterprise", version="0.3")
CORS_ORIGINS = [x.strip() for x in os.getenv("LEGALII_CORS_ORIGINS", "*").split(",") if x.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _load_json(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _audit(event: str, payload: Dict[str, Any]):
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "event": event,
        **payload,
    }
    with open(AUDIT_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _enqueue_review(item: Dict[str, Any]):
    REVIEW_QUEUE.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "id": hashlib.sha256(json.dumps(item, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:16],
        "ts": datetime.now().isoformat(timespec="seconds"),
        "status": "pending",
        **item,
    }
    with open(REVIEW_QUEUE, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def _load_review_queue() -> list[Dict[str, Any]]:
    if not REVIEW_QUEUE.exists():
        return []
    items: list[Dict[str, Any]] = []
    with open(REVIEW_QUEUE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except Exception:
                continue
    return items


def _save_review_queue(items: list[Dict[str, Any]]):
    REVIEW_QUEUE.parent.mkdir(parents=True, exist_ok=True)
    with open(REVIEW_QUEUE, "w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")


def _parse_key_registry() -> Dict[str, Dict[str, str]]:
    if not API_KEYS_JSON:
        return {}
    try:
        data = json.loads(API_KEYS_JSON)
        if isinstance(data, dict):
            return {
                str(k): {
                    "user": str((v or {}).get("user", "user")),
                    "role": str((v or {}).get("role", "assistant")),
                }
                for k, v in data.items()
            }
    except Exception:
        return {}
    return {}


def _load_user_store() -> Dict[str, Any]:
    if not USER_STORE.exists():
        return {"users": []}
    try:
        data = json.loads(USER_STORE.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("users"), list):
            return data
    except Exception:
        pass
    return {"users": []}


def _save_user_store(data: Dict[str, Any]):
    USER_STORE.parent.mkdir(parents=True, exist_ok=True)
    USER_STORE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _hash_password(password: str, salt_hex: str | None = None) -> str:
    salt = bytes.fromhex(salt_hex) if salt_hex else secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
    return f"pbkdf2_sha256$120000${salt.hex()}${dk.hex()}"


def _verify_password(password: str, encoded: str) -> bool:
    try:
        algo, rounds, salt_hex, digest_hex = encoded.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        test = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(rounds)).hex()
        return hmac.compare_digest(test, digest_hex)
    except Exception:
        return False


def _issue_token(identity: Dict[str, str]) -> str:
    exp = int(datetime.now().timestamp()) + TOKEN_TTL_SECONDS
    payload = {"user": identity.get("user"), "role": identity.get("role"), "exp": exp}
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    sig = hmac.new(TOKEN_SECRET.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    body = base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")
    return f"legtk_{body}.{sig}"


def _decode_token(token: str) -> Dict[str, str] | None:
    if not token.startswith("legtk_") or "." not in token:
        return None
    body, sig = token[6:].rsplit(".", 1)
    try:
        padded = body + "=" * (-len(body) % 4)
        raw = base64.urlsafe_b64decode(padded.encode("utf-8"))
        expected = hmac.new(TOKEN_SECRET.encode("utf-8"), raw, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig):
            return None
        payload = json.loads(raw.decode("utf-8"))
        if int(payload.get("exp", 0)) < int(datetime.now().timestamp()):
            return None
        return {"user": str(payload.get("user", "user")), "role": str(payload.get("role", "assistant"))}
    except Exception:
        return None


def _resolve_identity(x_api_key: str | None) -> Dict[str, str]:
    key = (x_api_key or "").strip()
    reg = _parse_key_registry()

    if key.startswith("legtk_"):
        ident = _decode_token(key)
        if ident:
            return ident

    if not REQUIRE_AUTH:
        if key and key in reg:
            return reg[key]
        return {"user": "local-dev", "role": "admin"}

    if reg and key in reg:
        return reg[key]
    if API_KEY and key == API_KEY:
        return {"user": "api-user", "role": "admin"}

    raise HTTPException(status_code=401, detail="Unauthorized")


def _require_roles(identity: Dict[str, str], allowed: list[str]):
    if identity.get("role") not in allowed:
        raise HTTPException(status_code=403, detail=f"Forbidden for role {identity.get('role')}")


def _detect_missing(required, docs):
    present = {d.get("doc_type") for d in docs}
    return [x for x in required if x not in present]


def _detect_conflicts(case: Dict[str, Any]):
    docs = case.get("documents", [])
    applicant = case.get("applicant", {})
    names, bdates, passnums = set(), set(), set()
    for d in docs:
        f = d.get("fields", {})
        if f.get("full_name"):
            names.add(f["full_name"])
        if f.get("birth_date"):
            bdates.add(f["birth_date"])
        if f.get("passport_number"):
            passnums.add(f["passport_number"])

    risks = []
    if len(names) > 1:
        risks.append("name_mismatch")
    if len(bdates) > 1:
        risks.append("birthdate_mismatch")
    if len(passnums) > 1:
        risks.append("passport_number_mismatch")
    if applicant.get("birth_date") and bdates and applicant["birth_date"] not in bdates:
        risks.append("birthdate_mismatch_with_profile")
    if applicant.get("passport_number") and passnums and applicant["passport_number"] not in passnums:
        risks.append("passport_mismatch_with_profile")
    return sorted(set(risks))


def _build_report(case: Dict[str, Any], rules: Dict[str, Any]):
    case_type = case.get("case_type", "asilo")
    rule = rules.get("case_types", {}).get(case_type, {})
    required = rule.get("required", [])
    optional = rule.get("optional", [])
    docs = case.get("documents", [])

    missing = _detect_missing(required, docs)
    risks = _detect_conflicts(case)
    score = max(0, 100 - min(len(missing) * 20, 60) - min(len(risks) * 10, 30))

    next_steps = []
    if missing:
        next_steps.append("Solicitar documentos faltantes antes de presentación.")
    if risks:
        next_steps.append("Resolver incoherencias de identidad/fechas con declaración y soporte documental.")
    if not next_steps:
        next_steps.append("Expediente listo para revisión final jurídica.")

    return {
        "success": True,
        "case_id": case.get("case_id"),
        "case_type": case_type,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "required_docs": required,
        "optional_docs": optional,
        "missing_docs": missing,
        "risk_flags": risks,
        "readiness_score": score,
        "next_steps": next_steps,
    }


def _quality_gate(case_data: Dict[str, Any], report: Dict[str, Any]) -> Dict[str, Any]:
    applicant = case_data.get("applicant", {}) or {}
    issues: list[str] = []

    full_name = (applicant.get("full_name") or "").strip()
    birth_date = (applicant.get("birth_date") or "").strip()
    passport = (applicant.get("passport_number") or "").strip()

    if not full_name or len(full_name) < 5:
        issues.append("missing_or_low_conf_full_name")
    if birth_date and not re.match(r"^\d{4}[-\./]\d{2}[-\./]\d{2}$", birth_date):
        issues.append("invalid_birth_date_format")
    if not birth_date:
        issues.append("missing_birth_date")
    if not passport or len(passport) < 5:
        issues.append("missing_or_low_conf_passport")

    if report.get("risk_flags"):
        issues.append("risk_flags_present")

    status = "READY"
    if STRICT_MODE and issues:
        status = "NEEDS_REVIEW"

    return {
        "status": status,
        "strict_mode": STRICT_MODE,
        "issues": issues,
        "blocking": bool(STRICT_MODE and issues),
    }


def _normalize_ocr_text(text: str) -> str:
    cleaned = text.replace("\r", "\n")
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _ocr_tesseract_best(image):
    try:
        import pytesseract  # type: ignore
        from PIL import ImageOps, ImageFilter  # type: ignore
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Image OCR support missing: install pillow+pytesseract+tesseract ({e})")

    variants = []
    gray = ImageOps.grayscale(image)
    variants.append(("orig", image))
    variants.append(("gray", gray))
    variants.append(("autocontrast", ImageOps.autocontrast(gray)))
    variants.append(("sharpen", gray.filter(ImageFilter.SHARPEN)))
    variants.append(("binary", gray.point(lambda x: 255 if x > 165 else 0, mode="1").convert("L")))

    configs = [
        "--oem 3 --psm 6",
        "--oem 3 --psm 4",
        "--oem 3 --psm 11",
    ]

    best_text = ""
    best_score = -1.0

    try:
        for vname, variant in variants:
            for cfg in configs:
                data = pytesseract.image_to_data(
                    variant,
                    lang="spa+eng",
                    config=cfg,
                    output_type=pytesseract.Output.DICT,
                )
                words = [w for w in data.get("text", []) if (w or "").strip()]
                confs = []
                for c in data.get("conf", []):
                    try:
                        cv = float(c)
                        if cv >= 0:
                            confs.append(cv)
                    except Exception:
                        pass

                text = pytesseract.image_to_string(variant, lang="spa+eng", config=cfg)
                text = _normalize_ocr_text(text)
                if not text:
                    continue

                avg_conf = (sum(confs) / len(confs)) if confs else 0.0
                coverage_bonus = min(len(words) / 120.0, 1.0) * 15.0
                score = avg_conf + coverage_bonus

                if score > best_score:
                    best_score = score
                    best_text = text
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Tesseract OCR runtime error: {e}")

    return best_text


def _ocr_easyocr_text(image) -> str:
    try:
        import numpy as np  # type: ignore
        import easyocr  # type: ignore
    except Exception:
        return ""

    try:
        arr = np.array(image)
        reader = easyocr.Reader(["es", "en"], gpu=False)
        parts = reader.readtext(arr, detail=0, paragraph=True)
        text = "\n".join(parts)
        return _normalize_ocr_text(text)
    except Exception:
        # Do not fail full OCR pipeline if easyocr model/network is unavailable.
        return ""


def _extract_text_from_upload(filename: str, content: bytes) -> str:
    name = filename.lower()

    if name.endswith((".txt", ".md", ".csv", ".log")):
        return content.decode("utf-8", errors="ignore")

    if name.endswith(".pdf"):
        try:
            from pypdf import PdfReader  # type: ignore
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"PDF support missing: install pypdf ({e})")
        reader = PdfReader(io.BytesIO(content))
        text = "\n".join((p.extract_text() or "") for p in reader.pages)
        return _normalize_ocr_text(text)

    if name.endswith(".docx"):
        try:
            import docx  # type: ignore
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"DOCX support missing: install python-docx ({e})")
        d = docx.Document(io.BytesIO(content))
        return _normalize_ocr_text("\n".join(p.text for p in d.paragraphs))

    if name.endswith((".png", ".jpg", ".jpeg", ".webp", ".tiff")):
        try:
            from PIL import Image  # type: ignore
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Image support missing: install pillow ({e})")

        image = Image.open(io.BytesIO(content))
        tesseract_text = _ocr_tesseract_best(image)
        easy_text = _ocr_easyocr_text(image)

        # Choose richer output; prefer longer valid text unless it's clearly noisy.
        candidates = [t for t in [tesseract_text, easy_text] if t and len(t) > 8]
        if not candidates:
            return _normalize_ocr_text(tesseract_text or easy_text)
        return max(candidates, key=len)

    raise HTTPException(status_code=400, detail="Unsupported file type. Use json/pdf/docx/txt/md/csv/log or image.")


def _infer_case_type_from_text(text: str) -> str:
    t = text.lower()
    if any(k in t for k in ["arraigo", "empadronamiento histórico", "informe de integración"]):
        return "arraigo_social"
    if any(k in t for k in ["nacionalidad", "ccse", "dele", "residencia"]):
        return "nacionalidad_residencia"
    return "asilo"


def _extract_first(pattern: str, text: str) -> str | None:
    m = re.search(pattern, text, flags=re.IGNORECASE)
    return m.group(1).strip() if m else None


def _infer_case_from_text(text: str, filename: str, rules: Dict[str, Any]) -> Dict[str, Any]:
    case_type = _infer_case_type_from_text(text)
    required = rules.get("case_types", {}).get(case_type, {}).get("required", [])
    t = text.lower()

    # loose keyword mapping for required doc detection
    keyword_map = {
        "pasaporte_o_id": ["pasaporte", "passport", "dni", "id"],
        "solicitud_asilo": ["solicitud de asilo", "asilo", "protección internacional"],
        "empadronamiento_o_domicilio": ["empadronamiento", "domicilio", "padrón"],
        "pruebas_relato": ["prueba", "evidencia", "amenaza", "persecución"],
        "pasaporte_completo": ["pasaporte", "passport"],
        "empadronamiento_historico": ["empadronamiento histórico", "histórico"],
        "antecedentes_penales_origen": ["antecedentes penales"],
        "contrato_trabajo_o_medios": ["contrato", "nómina", "medios económicos"],
        "pasaporte": ["pasaporte", "passport"],
        "tarjeta_residencia": ["nie", "tarjeta de residencia"],
        "certificado_nacimiento": ["certificado de nacimiento", "nacimiento"],
        "antecedentes_penales": ["antecedentes penales"],
        "ccse_dele_si_aplica": ["ccse", "dele"],
    }

    docs = []
    for req in required:
        if any(k in t for k in keyword_map.get(req, [req.replace("_", " ")])):
            docs.append({"doc_type": req, "fields": {}})

    full_name = _extract_first(r"(?:name|nombre)[:\s]+([A-Za-zÀ-ÿ\-\s]{5,})", text)
    birth_date = _extract_first(r"(?:fecha de nacimiento|birth\s*date)[:\s]+([0-9\-/\.]{8,12})", text)
    passport = _extract_first(r"(?:passport|pasaporte|n[úu]mero\s*de\s*pasaporte)[:\s]+([A-Z0-9\-]{5,})", text)

    return {
        "case_id": f"INGEST-{Path(filename).stem[:24]}",
        "case_type": case_type,
        "applicant": {
            "full_name": full_name,
            "birth_date": birth_date,
            "passport_number": passport,
        },
        "documents": docs,
        "raw_text_chars": len(text),
    }


def _safe_name(name: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9._-]+", "_", name).strip("_")
    return clean or "file"


def _safe_case_id(case_id: str) -> str:
    cid = re.sub(r"[^A-Za-z0-9._-]+", "-", (case_id or "").strip())
    return cid[:80] or f"case-{int(datetime.now().timestamp())}"


def _case_path(case_id: str) -> Path:
    return CASES_DIR / f"{_safe_case_id(case_id)}.json"


def _load_case(case_id: str) -> Dict[str, Any]:
    p = _case_path(case_id)
    if not p.exists():
        raise HTTPException(status_code=404, detail="case not found")
    return json.loads(p.read_text(encoding="utf-8"))


def _save_case(case: Dict[str, Any]):
    CASES_DIR.mkdir(parents=True, exist_ok=True)
    p = _case_path(str(case.get("id")))
    p.write_text(json.dumps(case, ensure_ascii=False, indent=2), encoding="utf-8")


def _append_case_report(case_id: str, report_row: Dict[str, Any]):
    case = _load_case(case_id)
    reports = case.get("reports", [])
    reports.append(report_row)
    case["reports"] = reports[-200:]
    case["updated_at"] = datetime.now().isoformat(timespec="seconds")
    _save_case(case)
    return case


class CasePayload(BaseModel):
    case_data: Dict[str, Any]




def _case_dossier_markdown(case: Dict[str, Any], review_items: list[Dict[str, Any]]) -> str:
    lines = [
        f"# LEGALII Dossier — {case.get('id')}",
        "",
        f"- Title: {case.get('title','')}",
        f"- Client: {case.get('client_name','')}",
        f"- Case type: {case.get('case_type','')}",
        f"- Status: {case.get('status','')}",
        f"- Owner: {case.get('owner','')}",
        f"- Updated: {case.get('updated_at','')}",
        "",
        "## Reports timeline",
    ]
    reports = case.get('reports', [])
    if not reports:
        lines.append('- No reports yet')
    else:
        for r in reports[-50:]:
            rep = r.get('report', {})
            rev = r.get('review', {})
            lines.append(f"- [{r.get('ts','')}] {r.get('filename','')} | score={rep.get('readiness_score')} | review={rev.get('status')}")
            risks = rep.get('risk_flags', [])
            miss = rep.get('missing_docs', [])
            if risks:
                lines.append(f"  - risks: {', '.join(risks[:6])}")
            if miss:
                lines.append(f"  - missing: {', '.join(miss[:6])}")

    lines += ["", "## Review decisions"]
    if not review_items:
        lines.append('- No review decisions yet')
    else:
        for it in review_items[-100:]:
            lines.append(f"- [{it.get('resolved_at') or it.get('ts')}] id={it.get('id')} status={it.get('status')} by={(it.get('resolved_by') or {}).get('user','')} note={it.get('resolution_note','')}")

    return '\n'.join(lines) + '\n'

def _report_markdown(report: Dict[str, Any]) -> str:
    lines = [
        f"# LEGALII Report — {report.get('case_id')}",
        "",
        f"- Case type: {report.get('case_type')}",
        f"- Created: {report.get('created_at')}",
        f"- Readiness: {report.get('readiness_score')}/100",
        "",
        "## Missing documents",
    ]
    missing = report.get("missing_docs", [])
    lines.extend([f"- {m}" for m in missing] if missing else ["- None"])
    lines += ["", "## Risk flags"]
    risks = report.get("risk_flags", [])
    lines.extend([f"- {r}" for r in risks] if risks else ["- None"])
    lines += ["", "## Next steps"]
    lines.extend([f"- {s}" for s in report.get("next_steps", [])])
    return "\n".join(lines) + "\n"


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "product": "legalii-enterprise",
        "env": APP_ENV,
        "auth_required": REQUIRE_AUTH,
    }


@app.get("/")
async def ui_root():
    return FileResponse(UI_DIR / "index.html")


@app.get("/ui/{asset}")
async def ui_assets(asset: str):
    path = UI_DIR / asset
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(path)


@app.get("/api/v1/pilot/sample/{sample_name}")
async def get_sample(sample_name: str, x_api_key: str | None = Header(default=None)):
    identity = _resolve_identity(x_api_key)
    path = FIXTURES_DIR / f"sample_case_{sample_name}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Sample not found")
    return _load_json(path)


@app.post("/api/v1/pilot/analyze")
async def analyze_case(
    payload: CasePayload,
    request: Request,
    x_api_key: str | None = Header(default=None),
):
    identity = _resolve_identity(x_api_key)
    rules = _load_json(RULES_PATH)
    report = _build_report(payload.case_data, rules)
    review = _quality_gate(payload.case_data, report)
    _audit(
        "analyze_case",
        {
            "client": request.client.host if request.client else None,
            "case_id": report.get("case_id"),
            "case_type": report.get("case_type"),
            "score": report.get("readiness_score"),
            "missing": len(report.get("missing_docs", [])),
            "risks": len(report.get("risk_flags", [])),
            "review_status": review.get("status"),
        },
    )
    queue_item = None
    if review.get("blocking"):
        queue_item = _enqueue_review({
            "source": "analyze_case",
            "case_id": report.get("case_id"),
            "case_type": report.get("case_type"),
            "review": review,
            "summary": {
                "score": report.get("readiness_score"),
                "missing": len(report.get("missing_docs", [])),
                "risks": len(report.get("risk_flags", [])),
            },
        })
    return {**report, "review": review, "review_queue": queue_item}


@app.post("/api/v1/pilot/ocr-image")
async def ocr_image(
    request: Request,
    file: UploadFile = File(...),
    x_api_key: str | None = Header(default=None),
):
    identity = _resolve_identity(x_api_key)
    name = file.filename or "uploaded"
    if not name.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".tiff")):
        raise HTTPException(status_code=400, detail="Upload image file")
    content = await file.read()
    text = _extract_text_from_upload(name, content)
    _audit("ocr_image", {"client": request.client.host if request.client else None, "filename": name, "chars": len(text)})
    return {
        "success": True,
        "filename": name,
        "text": text,
        "chars": len(text),
        "note": "OCR is probabilistic; legal review is required for critical fields."
    }


@app.post("/api/v1/pilot/analyze-upload")
async def analyze_upload(
    request: Request,
    file: UploadFile = File(...),
    x_api_key: str | None = Header(default=None),
):
    identity = _resolve_identity(x_api_key)

    content = await file.read()
    name = file.filename or "uploaded"

    # JSON remains supported as native structured path
    if name.lower().endswith(".json"):
        try:
            case_data = json.loads(content.decode("utf-8"))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")
    else:
        rules = _load_json(RULES_PATH)
        text = _extract_text_from_upload(name, content)
        if not text.strip():
            raise HTTPException(status_code=400, detail="No text extracted from document")
        case_data = _infer_case_from_text(text, name, rules)

    rules = _load_json(RULES_PATH)
    report = _build_report(case_data, rules)
    review = _quality_gate(case_data, report)
    _audit(
        "analyze_upload",
        {
            "client": request.client.host if request.client else None,
            "filename": name,
            "case_id": report.get("case_id"),
            "case_type": report.get("case_type"),
            "score": report.get("readiness_score"),
            "missing": len(report.get("missing_docs", [])),
            "risks": len(report.get("risk_flags", [])),
            "review_status": review.get("status"),
        },
    )
    queue_item = None
    if review.get("blocking"):
        queue_item = _enqueue_review({
            "source": "analyze_upload",
            "filename": name,
            "case_id": report.get("case_id"),
            "case_type": report.get("case_type"),
            "review": review,
            "summary": {
                "score": report.get("readiness_score"),
                "missing": len(report.get("missing_docs", [])),
                "risks": len(report.get("risk_flags", [])),
            },
        })
    return {
        **report,
        "review": review,
        "review_queue": queue_item,
        "ingestion": {
            "filename": name,
            "mode": "structured-json" if name.lower().endswith(".json") else "text-inferred",
        },
    }


@app.post("/api/v1/pilot/analyze-batch")
async def analyze_batch(
    request: Request,
    files: list[UploadFile] = File(...),
    x_api_key: str | None = Header(default=None),
):
    identity = _resolve_identity(x_api_key)
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    rules = _load_json(RULES_PATH)
    texts: list[str] = []
    names: list[str] = []

    for f in files:
        content = await f.read()
        fname = f.filename or "uploaded"
        names.append(fname)
        if fname.lower().endswith(".json"):
            try:
                case_data = json.loads(content.decode("utf-8"))
                report = _build_report(case_data, rules)
                review = _quality_gate(case_data, report)
                _audit("analyze_batch_item", {"client": request.client.host if request.client else None, "filename": fname, "score": report.get("readiness_score"), "review_status": review.get("status")})
                return {**report, "review": review, "ingestion": {"mode": "structured-json-batch", "files": names}}
            except Exception:
                pass
        try:
            txt = _extract_text_from_upload(fname, content)
            if txt.strip():
                texts.append(txt)
        except HTTPException:
            continue

    if not texts:
        raise HTTPException(status_code=400, detail="No readable text extracted from uploaded files")

    merged = "\n\n".join(texts)
    case_data = _infer_case_from_text(merged, "batch_upload", rules)
    report = _build_report(case_data, rules)
    review = _quality_gate(case_data, report)
    _audit(
        "analyze_batch",
        {
            "client": request.client.host if request.client else None,
            "files": names,
            "score": report.get("readiness_score"),
            "missing": len(report.get("missing_docs", [])),
            "risks": len(report.get("risk_flags", [])),
            "review_status": review.get("status"),
        },
    )
    queue_item = None
    if review.get("blocking"):
        queue_item = _enqueue_review({
            "source": "analyze_batch",
            "files": names,
            "case_id": report.get("case_id"),
            "case_type": report.get("case_type"),
            "review": review,
            "summary": {
                "score": report.get("readiness_score"),
                "missing": len(report.get("missing_docs", [])),
                "risks": len(report.get("risk_flags", [])),
            },
        })
    return {**report, "review": review, "review_queue": queue_item, "ingestion": {"mode": "text-inferred-batch", "files": names, "merged_chars": len(merged)}}


@app.post("/api/v1/pilot/export-markdown", response_class=PlainTextResponse)
async def export_markdown(
    payload: CasePayload,
    x_api_key: str | None = Header(default=None),
):
    identity = _resolve_identity(x_api_key)
    rules = _load_json(RULES_PATH)
    report = _build_report(payload.case_data, rules)
    review = _quality_gate(payload.case_data, report)
    if review.get("blocking"):
        raise HTTPException(status_code=409, detail={"message": "Strict mode block: review required before export", "review": review})
    return _report_markdown(report)


@app.post("/api/v1/pilot/context-from-bundle", response_class=PlainTextResponse)
async def context_from_bundle(
    bundle_id: str,
    x_api_key: str | None = Header(default=None),
):
    identity = _resolve_identity(x_api_key)
    bundle_path = INGEST_DIR / bundle_id / "context.txt"
    if not bundle_path.exists():
        raise HTTPException(status_code=404, detail="Bundle context not found")
    txt = bundle_path.read_text(encoding="utf-8")
    prompt = (
        "SYSTEM: You are a legal document analyst. Preserve every detail, do not hallucinate.\n"
        "TASK: Extract structured facts, timeline, contradictions, and missing evidence.\n\n"
        "CONTEXT_START\n"
        f"{txt}\n"
        "CONTEXT_END\n"
    )
    return prompt


@app.post("/api/v1/pilot/ingest-bundle")
async def ingest_bundle(
    request: Request,
    files: list[UploadFile] = File(...),
    x_api_key: str | None = Header(default=None),
):
    """
    Extract full text from uploaded documents and persist:
    - one text file per source document
    - merged context.txt for prompt ingestion
    """
    identity = _resolve_identity(x_api_key)
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    bundle_id = f"bundle-{ts}"
    out_dir = INGEST_DIR / bundle_id
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, Any] = {
        "bundle_id": bundle_id,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "files": [],
    }
    merged_parts: list[str] = []

    for idx, f in enumerate(files, start=1):
        raw = await f.read()
        original_name = f.filename or f"file_{idx}"
        safe = _safe_name(original_name)

        try:
            text = _extract_text_from_upload(original_name, raw)
        except HTTPException as e:
            manifest["files"].append(
                {
                    "name": original_name,
                    "saved": None,
                    "status": "error",
                    "error": e.detail,
                }
            )
            continue

        if not text.strip():
            manifest["files"].append(
                {
                    "name": original_name,
                    "saved": None,
                    "status": "empty",
                    "chars": 0,
                }
            )
            continue

        txt_name = f"{idx:03d}_{safe}.txt"
        txt_path = out_dir / txt_name
        txt_path.write_text(text, encoding="utf-8")

        sha = hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()
        manifest["files"].append(
            {
                "name": original_name,
                "saved": txt_name,
                "status": "ok",
                "chars": len(text),
                "sha256": sha,
            }
        )
        merged_parts.append(f"### SOURCE: {original_name}\n\n{text}")

    merged = "\n\n".join(merged_parts).strip()
    context_path = out_dir / "context.txt"
    context_path.write_text(merged, encoding="utf-8")

    manifest["context_file"] = "context.txt"
    manifest["context_chars"] = len(merged)
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    _audit(
        "ingest_bundle",
        {
            "client": request.client.host if request.client else None,
            "bundle_id": bundle_id,
            "files_total": len(files),
            "files_ok": sum(1 for x in manifest["files"] if x.get("status") == "ok"),
            "context_chars": manifest["context_chars"],
        },
    )

    return {
        "success": True,
        "bundle_id": bundle_id,
        "output_dir": str(out_dir),
        "context_file": str(context_path),
        "manifest_file": str(manifest_path),
        "context_chars": manifest["context_chars"],
        "files": manifest["files"],
        "warning": "OCR may contain errors. Human legal verification is mandatory.",
    }


class ReviewOverridePayload(BaseModel):
    case_data: Dict[str, Any]
    reviewer_note: str




class CaseCreatePayload(BaseModel):
    case_id: str
    case_type: str
    title: str = ""
    client_name: str = ""
    status: str = "draft"
    owner: str = ""
    case_data: Dict[str, Any] = {}


class CasePatchPayload(BaseModel):
    title: str | None = None
    client_name: str | None = None
    status: str | None = None
    owner: str | None = None
    case_type: str | None = None


@app.post("/api/v1/cases")
async def cases_create(payload: CaseCreatePayload, request: Request, x_api_key: str | None = Header(default=None)):
    identity = _resolve_identity(x_api_key)
    _require_roles(identity, ["admin", "lawyer", "assistant"])
    case_id = _safe_case_id(payload.case_id)
    path = _case_path(case_id)
    if path.exists():
        raise HTTPException(status_code=409, detail="case already exists")
    now = datetime.now().isoformat(timespec="seconds")
    row = {
        "id": case_id,
        "case_type": payload.case_type,
        "title": payload.title,
        "client_name": payload.client_name,
        "status": payload.status,
        "owner": payload.owner or identity.get("user"),
        "case_data": payload.case_data,
        "reports": [],
        "created_at": now,
        "updated_at": now,
    }
    _save_case(row)
    _audit("case_create", {"client": request.client.host if request.client else None, "case_id": case_id, "user": identity.get("user")})
    return {"success": True, "case": row}


@app.get("/api/v1/cases")
async def cases_list(x_api_key: str | None = Header(default=None), q: str = "", status: str = "", limit: int = 200):
    identity = _resolve_identity(x_api_key)
    _require_roles(identity, ["admin", "lawyer", "assistant"])
    CASES_DIR.mkdir(parents=True, exist_ok=True)
    items = []
    for p in sorted(CASES_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            c = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if status and str(c.get("status", "")) != status:
            continue
        if q:
            text = f"{c.get('id','')} {c.get('title','')} {c.get('client_name','')}".lower()
            if q.lower() not in text:
                continue
        items.append({
            "id": c.get("id"),
            "title": c.get("title"),
            "client_name": c.get("client_name"),
            "case_type": c.get("case_type"),
            "status": c.get("status"),
            "owner": c.get("owner"),
            "updated_at": c.get("updated_at"),
            "reports_count": len(c.get("reports", [])),
        })
        if len(items) >= max(1, min(limit, 1000)):
            break
    return {"count": len(items), "items": items}


@app.get("/api/v1/cases/{case_id}")
async def cases_get(case_id: str, x_api_key: str | None = Header(default=None)):
    identity = _resolve_identity(x_api_key)
    _require_roles(identity, ["admin", "lawyer", "assistant"])
    return {"success": True, "case": _load_case(case_id)}


@app.patch("/api/v1/cases/{case_id}")
async def cases_patch(case_id: str, payload: CasePatchPayload, request: Request, x_api_key: str | None = Header(default=None)):
    identity = _resolve_identity(x_api_key)
    _require_roles(identity, ["admin", "lawyer", "assistant"])
    case = _load_case(case_id)
    allowed_flow = {
        "draft": ["in_review", "closed"],
        "in_review": ["ready", "closed", "draft"],
        "ready": ["closed", "in_review"],
        "closed": ["closed"],
    }
    for k in ["title", "client_name", "owner", "case_type"]:
        v = getattr(payload, k)
        if v is not None:
            case[k] = v

    if payload.status is not None:
        cur = str(case.get("status", "draft"))
        nxt = str(payload.status)
        if nxt not in ["draft", "in_review", "ready", "closed"]:
            raise HTTPException(status_code=400, detail="invalid status")
        if nxt != cur and nxt not in allowed_flow.get(cur, []):
            raise HTTPException(status_code=400, detail=f"invalid status transition: {cur} -> {nxt}")
        case["status"] = nxt
    case["updated_at"] = datetime.now().isoformat(timespec="seconds")
    _save_case(case)
    _audit("case_patch", {"client": request.client.host if request.client else None, "case_id": case.get("id"), "user": identity.get("user")})
    return {"success": True, "case": case}


@app.post("/api/v1/cases/{case_id}/analyze-upload")
async def case_analyze_upload(case_id: str, request: Request, file: UploadFile = File(...), x_api_key: str | None = Header(default=None)):
    identity = _resolve_identity(x_api_key)
    _require_roles(identity, ["admin", "lawyer", "assistant"])
    case = _load_case(case_id)
    content = await file.read()
    name = file.filename or "uploaded"
    rules = _load_json(RULES_PATH)

    if name.lower().endswith(".json"):
        try:
            case_data = json.loads(content.decode("utf-8"))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")
    else:
        text = _extract_text_from_upload(name, content)
        if not text.strip():
            raise HTTPException(status_code=400, detail="No text extracted from document")
        case_data = _infer_case_from_text(text, name, rules)

    report = _build_report(case_data, rules)
    review = _quality_gate(case_data, report)
    report_row = {
        "id": hashlib.sha256(f"{case_id}:{datetime.now().isoformat()}:{name}".encode("utf-8")).hexdigest()[:16],
        "ts": datetime.now().isoformat(timespec="seconds"),
        "filename": name,
        "report": report,
        "review": review,
    }
    case = _append_case_report(case_id, report_row)

    queue_item = None
    if review.get("blocking"):
        queue_item = _enqueue_review({
            "source": "case_analyze_upload",
            "case_ref": case_id,
            "filename": name,
            "case_id": report.get("case_id"),
            "case_type": report.get("case_type"),
            "review": review,
            "summary": {
                "score": report.get("readiness_score"),
                "missing": len(report.get("missing_docs", [])),
                "risks": len(report.get("risk_flags", [])),
            },
        })

    _audit("case_analyze_upload", {"client": request.client.host if request.client else None, "case_ref": case_id, "filename": name, "user": identity.get("user"), "review_status": review.get("status")})
    return {"success": True, "case_id": case_id, "report_entry": report_row, "review_queue": queue_item, "case_reports_count": len(case.get("reports", []))}


@app.get("/api/v1/cases/{case_id}/reports")
async def case_reports(case_id: str, x_api_key: str | None = Header(default=None), limit: int = 50):
    identity = _resolve_identity(x_api_key)
    _require_roles(identity, ["admin", "lawyer", "assistant"])
    case = _load_case(case_id)
    reports = case.get("reports", [])
    n = max(1, min(limit, 500))
    return {"count": len(reports), "items": reports[-n:]}


@app.get("/api/v1/cases/{case_id}/dossier-markdown", response_class=PlainTextResponse)
async def case_dossier_markdown(case_id: str, x_api_key: str | None = Header(default=None)):
    identity = _resolve_identity(x_api_key)
    _require_roles(identity, ["admin", "lawyer", "assistant"])
    case = _load_case(case_id)
    review_items = [x for x in _load_review_queue() if str(x.get("case_ref", "")) == case_id and x.get("status") in ["approved", "rejected"]]
    return _case_dossier_markdown(case, review_items)


@app.get("/api/v1/cases/{case_id}/dossier-pdf")
async def case_dossier_pdf(case_id: str, x_api_key: str | None = Header(default=None)):
    identity = _resolve_identity(x_api_key)
    _require_roles(identity, ["admin", "lawyer", "assistant"])
    case = _load_case(case_id)
    review_items = [x for x in _load_review_queue() if str(x.get("case_ref", "")) == case_id and x.get("status") in ["approved", "rejected"]]
    md = _case_dossier_markdown(case, review_items)

    try:
        from reportlab.lib.pagesizes import A4  # type: ignore
        from reportlab.pdfgen import canvas  # type: ignore
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"PDF export dependency missing (reportlab): {e}")

    packet = io.BytesIO()
    c = canvas.Canvas(packet, pagesize=A4)
    w, h = A4
    y = h - 40
    c.setFont("Helvetica", 10)
    for line in md.splitlines():
        c.drawString(40, y, line[:120])
        y -= 14
        if y < 40:
            c.showPage()
            c.setFont("Helvetica", 10)
            y = h - 40
    c.showPage()
    c.save()
    data = packet.getvalue()
    return Response(content=data, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename=legalii_dossier_{case_id}.pdf"})

class LoginPayload(BaseModel):
    username: str
    password: str


class UserUpsertPayload(BaseModel):
    username: str
    password: str
    role: str = "assistant"
    enabled: bool = True


@app.post("/api/v1/auth/login")
async def auth_login(payload: LoginPayload, request: Request):
    users = _load_user_store().get("users", [])
    username = payload.username.strip().lower()
    for u in users:
        if str(u.get("username", "")).lower() != username:
            continue
        if not u.get("enabled", True):
            raise HTTPException(status_code=403, detail="User is disabled")
        if not _verify_password(payload.password, str(u.get("password_hash", ""))):
            break
        identity = {"user": str(u.get("username")), "role": str(u.get("role", "assistant"))}
        token = _issue_token(identity)
        _audit("auth_login", {
            "client": request.client.host if request.client else None,
            "user": identity["user"],
            "role": identity["role"],
            "ok": True,
        })
        return {"success": True, "token": token, "token_type": "x-api-key", "expires_in": TOKEN_TTL_SECONDS, "identity": identity}

    _audit("auth_login", {
        "client": request.client.host if request.client else None,
        "user": payload.username,
        "ok": False,
    })
    raise HTTPException(status_code=401, detail="Invalid credentials")


@app.get("/api/v1/auth/me")
async def auth_me(x_api_key: str | None = Header(default=None)):
    identity = _resolve_identity(x_api_key)
    return {"success": True, "identity": identity}


@app.get("/api/v1/auth/users")
async def auth_users(x_api_key: str | None = Header(default=None)):
    identity = _resolve_identity(x_api_key)
    _require_roles(identity, ["admin"])
    users = _load_user_store().get("users", [])
    out = [{
        "username": u.get("username"),
        "role": u.get("role", "assistant"),
        "enabled": bool(u.get("enabled", True)),
    } for u in users]
    return {"count": len(out), "items": out}


@app.post("/api/v1/auth/users")
async def auth_users_upsert(payload: UserUpsertPayload, x_api_key: str | None = Header(default=None)):
    identity = _resolve_identity(x_api_key)
    _require_roles(identity, ["admin"])
    if payload.role not in ["admin", "lawyer", "assistant"]:
        raise HTTPException(status_code=400, detail="role must be admin|lawyer|assistant")
    username = payload.username.strip()
    if not username or len(payload.password) < 8:
        raise HTTPException(status_code=400, detail="username required; password min 8 chars")

    data = _load_user_store()
    users = data.get("users", [])
    updated = False
    for u in users:
        if str(u.get("username", "")).lower() == username.lower():
            u["password_hash"] = _hash_password(payload.password)
            u["role"] = payload.role
            u["enabled"] = payload.enabled
            updated = True
            break
    if not updated:
        users.append({
            "username": username,
            "password_hash": _hash_password(payload.password),
            "role": payload.role,
            "enabled": payload.enabled,
        })

    data["users"] = users
    _save_user_store(data)
    return {"success": True, "updated": updated, "username": username, "role": payload.role, "enabled": payload.enabled}


@app.get("/api/v1/system/config")
async def system_config(x_api_key: str | None = Header(default=None)):
    identity = _resolve_identity(x_api_key)
    _require_roles(identity, ["admin"])
    return {
        "product": "LEGALII Enterprise",
        "env": APP_ENV,
        "auth_required": REQUIRE_AUTH,
        "auth_modes": ["api_key", "user_password_token"],
        "users_count": len(_load_user_store().get("users", [])),
        "strict_mode": STRICT_MODE,
        "cors_origins": CORS_ORIGINS,
        "ingest_dir": str(INGEST_DIR),
        "audit_log": str(AUDIT_LOG),
        "review_log": str(REVIEW_LOG),
        "user_store": str(USER_STORE),
        "cases_dir": str(CASES_DIR),
    }


@app.get("/api/v1/pilot/review-queue")
async def review_queue(x_api_key: str | None = Header(default=None), status: str = "pending"):
    identity = _resolve_identity(x_api_key)
    _require_roles(identity, ["admin", "lawyer", "assistant"])
    items = _load_review_queue()
    if status:
        items = [x for x in items if x.get("status") == status]
    return {"count": len(items), "items": items[-200:]}


class ReviewResolvePayload(BaseModel):
    id: str
    decision: str  # approved|rejected
    note: str


@app.post("/api/v1/pilot/review-resolve")
async def review_resolve(
    payload: ReviewResolvePayload,
    request: Request,
    x_api_key: str | None = Header(default=None),
):
    identity = _resolve_identity(x_api_key)
    _require_roles(identity, ["admin", "lawyer"])
    if payload.decision not in ["approved", "rejected"]:
        raise HTTPException(status_code=400, detail="decision must be approved|rejected")

    items = _load_review_queue()
    found = False
    for it in items:
        if it.get("id") == payload.id and it.get("status") == "pending":
            it["status"] = payload.decision
            it["resolved_at"] = datetime.now().isoformat(timespec="seconds")
            it["resolved_by"] = identity
            it["resolution_note"] = payload.note
            found = True
            break
    if not found:
        raise HTTPException(status_code=404, detail="pending review item not found")

    _save_review_queue(items)

    # If review item references a case, auto-update case status
    selected = next((x for x in items if x.get("id") == payload.id), None)
    cref = str((selected or {}).get("case_ref", "")).strip()
    if cref:
        try:
            case = _load_case(cref)
            if payload.decision == "approved":
                case["status"] = "ready"
            elif payload.decision == "rejected":
                case["status"] = "in_review"
            case["updated_at"] = datetime.now().isoformat(timespec="seconds")
            _save_case(case)
        except Exception:
            pass

    REVIEW_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(REVIEW_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "ts": datetime.now().isoformat(timespec="seconds"),
            "event": "review_resolve",
            "id": payload.id,
            "decision": payload.decision,
            "note": payload.note,
            "user": identity.get("user"),
            "role": identity.get("role"),
            "client": request.client.host if request.client else None,
        }, ensure_ascii=False) + "\n")

    return {"success": True, "id": payload.id, "decision": payload.decision}


@app.post("/api/v1/pilot/review-override")
async def review_override(
    payload: ReviewOverridePayload,
    request: Request,
    x_api_key: str | None = Header(default=None),
):
    identity = _resolve_identity(x_api_key)
    _require_roles(identity, ["admin", "lawyer"])

    rules = _load_json(RULES_PATH)
    report = _build_report(payload.case_data, rules)
    review = _quality_gate(payload.case_data, report)

    REVIEW_LOG.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "user": identity.get("user"),
        "role": identity.get("role"),
        "client": request.client.host if request.client else None,
        "case_id": report.get("case_id"),
        "review_status_before": review.get("status"),
        "note": payload.reviewer_note,
    }
    with open(REVIEW_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")

    return {
        "success": True,
        "override": True,
        "by": identity,
        "report": report,
        "review_before": review,
    }


@app.post("/api/v1/pilot/export-pdf")
async def export_pdf(
    payload: CasePayload,
    x_api_key: str | None = Header(default=None),
):
    identity = _resolve_identity(x_api_key)
    rules = _load_json(RULES_PATH)
    report = _build_report(payload.case_data, rules)
    review = _quality_gate(payload.case_data, report)
    if review.get("blocking"):
        raise HTTPException(status_code=409, detail={"message": "Strict mode block: review required before export", "review": review})

    try:
        from reportlab.lib.pagesizes import A4  # type: ignore
        from reportlab.pdfgen import canvas  # type: ignore
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"PDF export dependency missing (reportlab): {e}")

    md = _report_markdown(report)
    packet = io.BytesIO()
    c = canvas.Canvas(packet, pagesize=A4)
    w, h = A4
    y = h - 40
    c.setFont("Helvetica", 10)
    for line in md.splitlines():
        c.drawString(40, y, line[:120])
        y -= 14
        if y < 40:
            c.showPage()
            c.setFont("Helvetica", 10)
            y = h - 40
    c.showPage()
    c.save()
    data = packet.getvalue()
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=legalii_report.pdf"},
    )
