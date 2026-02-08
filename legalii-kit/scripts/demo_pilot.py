#!/usr/bin/env python3
import json
import argparse
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RULES_PATH = ROOT / "config" / "06-ruleset-extranjeria-v1.json"
OUT_DIR = ROOT / "demo" / "out"


def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def detect_missing(required, docs):
    present = {d.get("doc_type") for d in docs}
    return [x for x in required if x not in present]


def detect_conflicts(case):
    docs = case.get("documents", [])
    applicant = case.get("applicant", {})
    risks = []

    names, bdates, passnums = set(), set(), set()
    for d in docs:
        f = d.get("fields", {})
        if f.get("full_name"):
            names.add(f["full_name"])
        if f.get("birth_date"):
            bdates.add(f["birth_date"])
        if f.get("passport_number"):
            passnums.add(f["passport_number"])

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


def build_report(case, rules):
    case_type = case.get("case_type", "asilo")
    rule = rules["case_types"].get(case_type, {})
    required = rule.get("required", [])
    optional = rule.get("optional", [])
    docs = case.get("documents", [])

    missing = detect_missing(required, docs)
    risks = detect_conflicts(case)

    score = 100 - min(len(missing) * 20, 60) - min(len(risks) * 10, 30)
    score = max(0, score)

    next_steps = []
    if missing:
        next_steps.append("Solicitar documentos faltantes antes de presentación.")
    if risks:
        next_steps.append("Resolver incoherencias de identidad/fechas con declaración y soporte documental.")
    if not next_steps:
        next_steps.append("Expediente listo para revisión final jurídica.")

    return {
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


def write_markdown(report, out_md: Path):
    lines = [
        f"# LEGALAIR Pilot Report — {report['case_id']}",
        "",
        f"- Case type: **{report['case_type']}**",
        f"- Created: `{report['created_at']}`",
        f"- Readiness score: **{report['readiness_score']}/100**",
        "",
        "## Missing documents",
    ]
    if report["missing_docs"]:
        lines += [f"- ❌ {m}" for m in report["missing_docs"]]
    else:
        lines.append("- ✅ None")

    lines += ["", "## Risk flags"]
    if report["risk_flags"]:
        lines += [f"- ⚠️ {r}" for r in report["risk_flags"]]
    else:
        lines.append("- ✅ None")

    lines += ["", "## Next steps"]
    lines += [f"- {s}" for s in report["next_steps"]]
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_html(report, out_html: Path):
    def li(items, empty):
        if not items:
            return f"<li>{empty}</li>"
        return "".join([f"<li>{x}</li>" for x in items])

    html = f"""<!doctype html>
<html><head><meta charset='utf-8'><title>LEGALAIR Report {report['case_id']}</title>
<style>body{{font-family:Arial;margin:24px;max-width:900px}} .score{{font-size:28px;font-weight:700}} .box{{padding:12px;border:1px solid #ddd;border-radius:8px;margin:12px 0}}</style>
</head><body>
<h1>LEGALAIR Pilot Report — {report['case_id']}</h1>
<div class='score'>Readiness score: {report['readiness_score']}/100</div>
<div class='box'><h3>Missing documents</h3><ul>{li(report['missing_docs'], 'None')}</ul></div>
<div class='box'><h3>Risk flags</h3><ul>{li(report['risk_flags'], 'None')}</ul></div>
<div class='box'><h3>Next steps</h3><ul>{li(report['next_steps'], 'No actions required')}</ul></div>
<p><small>Created: {report['created_at']}</small></p>
</body></html>"""
    out_html.write_text(html, encoding="utf-8")


def run_case(case_path: Path, rules: dict):
    case = load_json(case_path)
    report = build_report(case, rules)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stem = case_path.stem
    out_json = OUT_DIR / f"{stem}_report.json"
    out_md = OUT_DIR / f"{stem}_report.md"
    out_html = OUT_DIR / f"{stem}_report.html"

    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(report, out_md)
    write_html(report, out_html)

    print(f"✅ {case.get('case_id')} | score={report['readiness_score']} | missing={len(report['missing_docs'])} | risks={len(report['risk_flags'])}")
    print(f"   -> {out_md}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="run all sample cases in demo/")
    parser.add_argument("--case", type=str, default="demo/sample_case_extranjeria.json", help="path to case json")
    args = parser.parse_args()

    rules = load_json(RULES_PATH)

    if args.all:
        for case_path in sorted((ROOT / "demo").glob("sample_case_*.json")):
            run_case(case_path, rules)
    else:
        run_case(ROOT / args.case, rules)


if __name__ == "__main__":
    main()
