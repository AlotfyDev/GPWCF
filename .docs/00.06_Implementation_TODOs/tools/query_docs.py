"""GPWCF documentation query tool.

Mines the .docs tree and produces one self-sufficient "dossier" markdown file per
implementation task under .docs/00.06_Implementation_TODOs/dossiers/, containing:

  - task metadata (from 00.05_Implementation_Tasks/<id>.json)
  - the related class/sequence/association/dependency diagrams, parsed:
      * .dot class diagrams  -> entities (label + tooltip design rules), edges
      * .puml sequence        -> participants, messages, notes
      * .puml association     -> classes with members, relationships
      * .dot dependency       -> allowed/forbidden dependency edges
  - relevant Primary Architecture contract documents, scored by mentions of the
    task's implementation classes (doc -> relevance list)
  - matching "resolved entity index" JSON notes per implementation class
  - acceptance criteria / DoD lifted verbatim from the task JSON

Usage:
    python query_docs.py                  # build all dossiers
    python query_docs.py 01_SPU           # build dossier(s) whose id contains the arg
    python query_docs.py --list           # list task ids
    python query_docs.py --search TERM    # grep-like search across all mined sources

Stdlib only; matches the Core standard-library-only baseline.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DOCS = PROJECT_ROOT / ".docs"
TASKS_DIR = DOCS / "00.05_Implementation_Tasks"
OUT_DIR = Path(__file__).resolve().parents[1] / "dossiers"

ARCH = DOCS / "00.00_Primary_Architecture"
DIAGRAMS = DOCS / "00.04_Architectural_Dependencies_Analysis"
DOT_CLASS_DIR = DIAGRAMS / "A_Class_Diagram_Code" / "03_Diagrams_Codes_Files"
ENTITY_INDEX_DIR = DIAGRAMS / "A_Class_Diagram_Code" / "02_Unique_Class_Entity_Resolved_index"
SEQ_DIR = DIAGRAMS / "B_Sequencial_Diagram_Code"
ASSOC_DIR = DIAGRAMS / "C_Association_Diagram_Code"
DEP_DIR = DIAGRAMS / "D_Architectural_Dependency_Diagram_Code"

# ----------------------------------------------------------------------------- loaders


def load_tasks() -> dict[str, dict]:
    tasks = {}
    for p in sorted(TASKS_DIR.glob("*.json")):
        tasks[p.stem] = json.loads(p.read_text(encoding="utf-8"))
    return tasks


def parse_dot(path: Path) -> dict:
    """Extract nodes (id -> label, tooltip) and edges from a graphviz .dot file.

    Handles both quoted ("Node Name") and bare (NodeName) identifiers, and
    attribute lists whose values may themselves contain brackets (record labels).
    """
    text = path.read_text(encoding="utf-8")
    nodes: dict[str, dict] = {}
    edges: list[dict] = []

    edge_re = re.compile(
        r'(?P<src>"[^"]+"|[\w]+)\s*->\s*(?P<dst>"[^"]+"|[\w]+)\s*(?:\[(?P<attrs>[^\n;]*?)\])?\s*;', re.S
    )
    node_re = re.compile(
        r'(?P<id>"[^"]+"|[\w]+)\s*\[(?P<attrs>[^\n;]*?)\]\s*;', re.S
    )

    def attr_dict(attrs: str) -> dict:
        out = {}
        for m in re.finditer(r'(\w+)\s*=\s*"((?:[^"\\]|\\.)*)"', attrs or ""):
            out[m.group(1)] = m.group(2).replace('\\"', '"').replace("\\l", " ").replace("\\n", " ")
        return out

    # First collect edges (so node regex doesn't eat edge endpoints as free nodes).
    for m in edge_re.finditer(text):
        edges.append(
            {
                "src": m.group("src").strip('"'),
                "dst": m.group("dst").strip('"'),
                **attr_dict(m.group("attrs")),
            }
        )
    # Remove edge statements before scanning nodes so endpoints aren't picked up as free nodes.
    nodes_text = edge_re.sub("", text)
    for m in node_re.finditer(nodes_text):
        node_id = m.group("id").strip('"')
        attrs = attr_dict(m.group("attrs"))
        if "label" in attrs or "tooltip" in attrs:
            nodes[node_id] = attrs
    return {"nodes": nodes, "edges": edges}


def parse_sequence_puml(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    participants: list[str] = []
    messages: list[str] = []
    notes: list[str] = []
    msg_re = re.compile(r"^[\w\"'][\w\"\[\], ]*\s*(?:-{1,2}>|\.{1,2}>|-->)\s*[\w\"'][\w\"\[\], ]*\s*:\s*(?P<msg>.+)$")
    note_re = re.compile(r"^note\s+(?:left|right|over)\b[^:]*:\s*(?P<text>.*)$")
    note_open_re = re.compile(r"^note\s+(?:left|right|over)\b")
    mode = None  # None | "note"
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(("@startuml", "@enduml", "skinparam", "title", "autonumber", "split", "end")):
            continue
        if line.startswith("participant"):
            participants.append(re.sub(r'^participant\s+"?([^"]*)"?.*$', r"\1", line))
            mode = None
            continue
        note_m = note_re.match(line)
        if note_m:
            mode = "note"
            notes.append(note_m.group("text").strip())
            continue
        if note_open_re.match(line):
            mode = "note"
            continue
        if line.startswith("end note"):
            mode = None
            continue
        msg_m = msg_re.match(line)
        if msg_m:
            mode = None
            messages.append(msg_m.group("msg").strip())
            continue
        if mode == "note":
            notes[-1] += " " + line
        elif messages:
            messages[-1] += " " + line  # continuation line of previous message
        elif line:
            participants.append(line)
    return {"participants": participants, "messages": messages, "notes": notes}


def parse_association_puml(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    classes: dict[str, dict] = {}
    relations: list[str] = []
    current: str | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(("@startuml", "@enduml", "skinparam")):
            continue
        m = re.match(r'^class\s+"([^"]+)"\s+as\s+(\w+)\s*(<<\w+>>)?\s*\{?', line)
        if m:
            current = m.group(2)
            classes[current] = {"name": m.group(1), "stereotype": (m.group(3) or "").strip("<>"), "members": []}
            continue
        if line.startswith(("title", "hide", "skin")):
            continue
        if re.match(r"^\w[\w\[\]]*\s*(?:-{2,}>|\.{2,}>|-{2,}|\.{2,}|->{1,2}|\.{1,2}>?)\s*\w", line):
            relations.append(line)
            current = None
            continue
        if current and line not in ("{", "}"):
            classes[current]["members"].append(line)
    return {"classes": classes, "relations": relations}


def dependency_rules(path: Path) -> list[str]:
    data = parse_dot(path)
    rules = []
    for e in data["edges"]:
        style = e.get("style", "")
        label = e.get("label", "")
        marker = " [FORBIDDEN]" if "FORBIDDEN" in label.upper() else ""
        rules.append(f'{e["src"]} -> {e["dst"]} : {label}{marker}' + (" (dashed)" if style == "dashed" else ""))
    return rules


# ------------------------------------------------------------------ contract mention index


def build_contract_index() -> list[dict]:
    """Scan every .json/.md under Primary Architecture; index name + text."""
    entries = []
    for p in sorted(ARCH.rglob("*")):
        if p.suffix.lower() not in (".json", ".md") or not p.is_file():
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        title = p.stem
        if p.suffix == ".json":
            try:
                data = json.loads(text)
                title = data.get("title", p.stem)
                text = json.dumps(data, ensure_ascii=False)
            except json.JSONDecodeError:
                pass
        entries.append({"rel": str(p.relative_to(PROJECT_ROOT)), "title": title, "text": text})
    return entries


def build_entity_index() -> list[dict]:
    entries = []
    for p in sorted(ENTITY_INDEX_DIR.glob("*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        text = json.dumps(data, ensure_ascii=False) if not isinstance(data, str) else data
        entries.append({"file": p.name, "data": data, "text": text})
    return entries


def class_variants(name: str) -> list[str]:
    """'StepProcessingUnit[TInput,TOutput]' -> ['StepProcessingUnit', 'Step Processing Unit', 'SPU', ...]"""
    base = re.sub(r"\[.*$", "", name).strip()
    variants = {base}
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", base)
    if spaced != base:
        variants.add(spaced)
    camel_words = re.findall(r"[A-Z]?[a-z0-9]+|[A-Z]+(?![a-z])", base)
    if camel_words:
        variants.add(" ".join(camel_words))
        # well-known abbreviations
        abbr = {"StepProcessingUnit": "SPU", "SPUValidatorResult": None}
        if base in abbr and abbr[base]:
            variants.add(abbr[base])
    return [v for v in variants if len(v) >= 3]


def _clean(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def find_entity_note(entity_index: list[dict], cls: str) -> dict | None:
    base = _clean(re.sub(r"\[.*$", "", cls))
    # 1) exact name match (ignoring the numeric prefix / non-alphanumerics)
    for e in entity_index:
        fname = re.sub(r"^\d+_", "", e["file"]).replace(".json", "")
        if _clean(fname) == base:
            return e
    # 2) file name starts with / contains the class name
    for e in entity_index:
        fname = re.sub(r"^\d+_", "", e["file"]).replace(".json", "")
        f = _clean(fname)
        if f.startswith(base) or base in f:
            return e
    # 3) content fallback: note whose text mentions the class name
    for e in entity_index:
        if base and base in _clean(e["text"][:4000]):
            return e
    return None


def compact(value, limit=700) -> str:
    """Render an arbitrary JSON value as a readable compact string."""
    if isinstance(value, str):
        return value[:limit] + ("…" if len(value) > limit else "")
    text = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
    text = re.sub(r"\s+", " ", text)
    return text[:limit] + ("…" if len(text) > limit else "")


def summarize_entity_note(note: dict | None) -> list[str]:
    if not note:
        return []
    lines = []
    data = note["data"]
    if isinstance(data, dict):
        for key, value in data.items():
            if key.lower() in ("documenttype",):
                continue
            lines.append(f"- **{key}:** {compact(value)}")
    else:
        lines.append(f"- {compact(data)}")
    return lines


# ------------------------------------------------------------------- dossier generation


def build_dossier(task_id: str, task: dict, contract_index: list[dict], entity_index: list[dict]) -> str:
    md: list[str] = []
    md.append(f"# Dossier — {task_id}")
    md.append("")
    md.append(f"> Auto-generated by `.docs/00.06_Implementation_TODOs/tools/query_docs.py`. Source of truth: the documents referenced here.")
    md.append("")
    md.append("## Task metadata")
    md.append("")
    md.append(f"- **Target:** {task['target']}")
    md.append(f"- **Category:** {task['category']} | **Priority:** {task['priority']} | **Effort:** {task['estimatedEffort']}")
    md.append(f"- **Depends on:** {', '.join(task['dependencies']) or '—'}")
    md.append(f"- **Description:** {task['description']}")
    md.append("")

    md.append("## Implementation classes")
    md.append("")
    for cls in task["implementationClasses"]:
        md.append(f"- `{cls}`")
    md.append("")

    # --- class diagram (task JSON paths omit the A_Class_Diagram_Code segment)
    rel = task.get("relatedDiagrams", {})
    cls_dot = rel.get("class")
    if cls_dot:
        path = DOT_CLASS_DIR / Path(cls_dot.replace("/", "\\")).name
        if path.exists():
            data = parse_dot(path)
            md.append(f"## Class diagram — `{cls_dot}`")
            md.append("")
            md.append("### Entities / rules (label → tooltip design rule)")
            md.append("")
            for node_id, attrs in data["nodes"].items():
                label = attrs.get("label", node_id).replace("|", " — ")
                tip = attrs.get("tooltip", "").strip()
                if tip:
                    md.append(f"- **{label}**: {tip}")
            md.append("")
            if data["edges"]:
                md.append("### Edges")
                md.append("")
                for e in data["edges"]:
                    md.append(f'- {e["src"]} → {e["dst"]} ({e.get("label", "")})')
                md.append("")

    # --- sequence diagram
    seq = rel.get("sequence")
    if seq:
        path = DIAGRAMS / seq.replace("/", "\\")
        if path.exists():
            data = parse_sequence_puml(path)
            md.append(f"## Sequence diagram — `{seq}`")
            md.append("")
            if data["participants"]:
                md.append(f"Participants: {', '.join(data['participants'])}")
            md.append("")
            md.append("### Flow")
            md.append("")
            for i, msg in enumerate(data["messages"], 1):
                md.append(f"{i}. {msg}")
            md.append("")
            for note in data["notes"]:
                if note.strip():
                    md.append(f"**Note:** {note}")
                    md.append("")

    # --- association diagram
    assoc = rel.get("association")
    if assoc:
        path = DIAGRAMS / assoc.replace("/", "\\")
        if path.exists():
            data = parse_association_puml(path)
            md.append(f"## Association diagram — `{assoc}`")
            md.append("")
            md.append("### Classes & members")
            md.append("")
            for alias, info in data["classes"].items():
                members = "; ".join(m for m in info["members"] if m) or "—"
                md.append(f'- **{info["name"]}** (<<{info["stereotype"]}>>): {members}')
            md.append("")
            md.append("### Relations")
            md.append("")
            for r in data["relations"]:
                md.append(f"- `{r}`")
            md.append("")

    # --- dependency diagrams
    dep_paths = [v for k, v in rel.items() if k.startswith("dependency")]
    if dep_paths:
        md.append("## Dependency rules (from dependency diagrams)")
        md.append("")
        for dep in dep_paths:
            path = DIAGRAMS / dep.replace("/", "\\")
            if path.exists():
                md.append(f"**`{dep}`**")
                md.append("")
                for rule in dependency_rules(path):
                    md.append(f"- {rule}")
                md.append("")

    # --- relevant contracts by class mention
    md.append("## Relevant Primary Architecture documents (scored by class mentions)")
    md.append("")
    scored = []
    for entry in contract_index:
        score = 0
        hits = []
        for cls in task["implementationClasses"]:
            for variant in class_variants(cls):
                c = len(re.findall(re.escape(variant), entry["text"], re.IGNORECASE))
                if c:
                    score += c
                    hits.append(variant)
        if score:
            scored.append((score, entry, hits))
    scored.sort(key=lambda x: -x[0])
    for score, entry, hits in scored[:12]:
        md.append(f'- `{entry["rel"]}` — **{entry["title"]}** (score {score}; mentions: {", ".join(sorted(set(hits))[:6])})')
    md.append("")

    # --- entity index notes
    md.append("## Resolved entity notes (from A_Class_Diagram_Code/02_Unique_Class_Entity_Resolved_index)")
    md.append("")
    for cls in task["implementationClasses"]:
        note = find_entity_note(entity_index, cls)
        md.append(f"### `{cls}`")
        if note:
            md.append(f'*file: `{note["file"]}`*')
            lines = summarize_entity_note(note)
            md.extend(lines if lines else ["- (empty note)"])
        else:
            md.append("- (no matching entity-index note found)")
        md.append("")

    # --- acceptance criteria + DoD
    md.append("## Acceptance criteria (verbatim from task JSON)")
    md.append("")
    for ac in task["acceptanceCriteria"]:
        md.append(f"- [ ] {ac}")
    md.append("")
    md.append("## Definition of Done (verbatim from task JSON)")
    md.append("")
    for d in task["definitionOfDone"]:
        md.append(f"- [ ] {d}")
    md.append("")
    md.append(f"## Test strategy")
    md.append("")
    md.append(task["testStrategy"])
    md.append("")
    return "\n".join(md)


# ----------------------------------------------------------------------------- search


def do_search(term: str, tasks: dict, contract_index: list[dict], entity_index: list[dict]) -> str:
    out = [f'Search results for "{term}"', ""]
    pat = re.compile(re.escape(term), re.IGNORECASE)

    out.append("## Task JSONs")
    for tid, t in tasks.items():
        blob = json.dumps(t, ensure_ascii=False)
        for m in pat.finditer(blob):
            s = max(0, m.start() - 80)
            out.append(f'- `{tid}`: …{blob[s:m.end() + 120]}…')
            break

    out.append("")
    out.append("## Primary Architecture documents")
    for entry in contract_index:
        for m in pat.finditer(entry["text"]):
            s = max(0, m.start() - 100)
            snippet = re.sub(r"\s+", " ", entry["text"][s:m.end() + 180])
            out.append(f'- `{entry["rel"]}`: …{snippet}…')
            break

    out.append("")
    out.append("## Entity index notes")
    for e in entity_index:
        for m in pat.finditer(e["text"]):
            s = max(0, m.start() - 80)
            snippet = re.sub(r"\s+", " ", e["text"][s:m.end() + 160])
            out.append(f'- `{e["file"]}`: …{snippet}…')
            break

    # diagrams
    out.append("")
    out.append("## Diagram code files")
    for d in (DOT_CLASS_DIR, SEQ_DIR, ASSOC_DIR, DEP_DIR):
        for p in sorted(d.glob("*")):
            if p.suffix.lower() not in (".dot", ".puml"):
                continue
            try:
                text = p.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for m in pat.finditer(text):
                s = max(0, m.start() - 80)
                snippet = re.sub(r"\s+", " ", text[s:m.end() + 160])
                out.append(f'- `{p.name}`: …{snippet}…')
                break
    return "\n".join(out)


# ----------------------------------------------------------------------------- main


def main(argv: list[str]) -> int:
    tasks = load_tasks()
    contract_index = build_contract_index()
    entity_index = build_entity_index()

    if "--list" in argv:
        for tid, t in tasks.items():
            print(f"{tid}: {t['target']} (deps: {', '.join(t['dependencies']) or '—'})")
        return 0

    if "--search" in argv:
        idx = argv.index("--search")
        term = argv[idx + 1]
        print(do_search(term, tasks, contract_index, entity_index))
        return 0

    filters = [a for a in argv if not a.startswith("--")]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    built = []
    for tid, task in tasks.items():
        if filters and not any(f.lower() in tid.lower() for f in filters):
            continue
        md = build_dossier(tid, task, contract_index, entity_index)
        out = OUT_DIR / f"{tid}.md"
        out.write_text(md, encoding="utf-8")
        built.append(str(out))
    for b in built:
        print(f"built: {b}")
    if not built:
        print("no tasks matched; use --list to see task ids")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
