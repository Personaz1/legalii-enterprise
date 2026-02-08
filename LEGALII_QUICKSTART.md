# LEGALII Quickstart

## 1) Local run (no docker, with preflight)
```bash
cd startup/legalii-openclaw
./scripts/legalii-kit.sh
```
Open: `http://127.0.0.1:8777/`

## 2) Local docker profile
```bash
cd startup/legalii-openclaw/enterprise
docker compose -f docker-compose.local.yml up -d
```

## 3) Server/enterprise profile (with preflight)
```bash
cd startup/legalii-openclaw
./scripts/legalii-enterprise-up.sh
```

## Security defaults
- local profile: auth disabled for fast dev
- enterprise profile: set API key and require auth
- audit log: `enterprise/logs/audit.log`

## API
- `GET /health`
- `GET /api/v1/pilot/sample/{extranjeria|arraigo|nacionalidad}`
- `POST /api/v1/pilot/analyze`
- `POST /api/v1/pilot/analyze-upload` (single file: json/pdf/docx/txt/md/csv/log/image)
- `POST /api/v1/pilot/analyze-batch` (multiple files)
- `POST /api/v1/pilot/ocr-image` (image text extraction)
- `POST /api/v1/pilot/ingest-bundle` (persist all extracted texts + context.txt)
- `POST /api/v1/pilot/context-from-bundle?bundle_id=...` (ready prompt context)

## OCR dependencies for images
```bash
python3 -m pip install --user pillow pytesseract pypdf python-docx
# plus system tesseract binary
```

## Strict legal mode
- `LEGALII_STRICT_MODE=true` by default.
- Reports include `review.status=NEEDS_REVIEW` when critical fields are weak/missing.
- Markdown/PDF export is blocked (HTTP 409) until review issues are resolved.
- Override endpoint for legal reviewer: `POST /api/v1/pilot/review-override`

## Roles / API keys
- Dev mode (`LEGALII_REQUIRE_AUTH=false`): local admin identity.
- Enterprise mode: set either
  - `LEGALII_API_KEY=<single key>` or
  - `LEGALII_API_KEYS_JSON='{"key1":{"user":"alice","role":"lawyer"},"key2":{"user":"ops","role":"admin"}}'`
- Admin endpoint: `GET /api/v1/system/config`


## Password auth (new)
- User store file: `enterprise/data/users.json`
- Login endpoint: `POST /api/v1/auth/login`
- Admin users management: `GET/POST /api/v1/auth/users`
- Login returns signed token (`legtk_...`) to pass in `x-api-key` header.
