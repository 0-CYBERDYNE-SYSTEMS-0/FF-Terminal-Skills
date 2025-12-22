import os
import re
from typing import Dict, List, Optional, Tuple


FRONTMATTER_DELIM = "---"


def _extract_frontmatter(content: str) -> Tuple[Optional[str], str]:
    lines = content.splitlines()
    if not lines or lines[0].strip() != FRONTMATTER_DELIM:
        return None, content

    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == FRONTMATTER_DELIM:
            end_idx = i
            break
    if end_idx is None:
        return None, content

    frontmatter = "\n".join(lines[1:end_idx]).strip("\n")
    body = "\n".join(lines[end_idx + 1 :]).lstrip("\n")
    return frontmatter, body


def _replace_or_add_field(frontmatter: str, field: str, value: str) -> str:
    lines = frontmatter.splitlines() if frontmatter else []
    pattern = re.compile(rf"^{re.escape(field)}\s*:\s*.*$")
    replaced = False
    for i, line in enumerate(lines):
        if pattern.match(line.strip()):
            lines[i] = f"{field}: {value}"
            replaced = True
            break
    if not replaced:
        lines.insert(0, f"{field}: {value}")
    return "\n".join(lines)


def _is_valid_name(name: str) -> bool:
    if not name or len(name) > 64:
        return False
    if name.startswith("-") or name.endswith("-"):
        return False
    if "--" in name:
        return False
    return bool(re.fullmatch(r"[a-z0-9-]+", name))


def _slugify(raw: str) -> str:
    if not raw:
        return "skill"
    slug = re.sub(r"[^a-z0-9]+", "-", raw.lower())
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    if not slug:
        slug = "skill"
    return slug[:64].strip("-") or "skill"


def _truncate_description(description: str) -> str:
    if len(description) <= 1024:
        return description
    return description[:1021].rstrip() + "..."


def normalize_skill_content(content: str, query: str) -> Tuple[str, str, List[str]]:
    warnings: List[str] = []
    frontmatter, body = _extract_frontmatter(content)

    name_match = re.search(r"(?m)^name\s*:\s*(.+)$", frontmatter or "")
    description_match = re.search(r"(?m)^description\s*:\s*(.+)$", frontmatter or "")

    raw_name = name_match.group(1).strip() if name_match else ""
    raw_description = description_match.group(1).strip() if description_match else ""

    if _is_valid_name(raw_name):
        skill_name = raw_name
    else:
        skill_name = _slugify(raw_name or query)
        if raw_name:
            warnings.append("Invalid skill name corrected to a valid format.")
        else:
            warnings.append("Missing skill name generated from query.")

    if raw_description:
        description = _truncate_description(raw_description)
        if description != raw_description:
            warnings.append("Description truncated to 1024 characters.")
    else:
        description = _truncate_description(
            f"Skill for {query}. Use when you need help with {query}."
        )
        warnings.append("Missing description generated from query.")

    frontmatter = frontmatter or ""
    frontmatter = _replace_or_add_field(frontmatter, "name", skill_name)
    frontmatter = _replace_or_add_field(frontmatter, "description", description)

    normalized = f"{FRONTMATTER_DELIM}\n{frontmatter}\n{FRONTMATTER_DELIM}\n\n{body}".rstrip() + "\n"
    return normalized, skill_name, warnings


def detect_referenced_files(content: str) -> List[str]:
    references = set()
    patterns = [
        r"\((references|scripts|assets)/[^)]+\)",
        r"(?m)^(references|scripts|assets)/\S+",
    ]
    for pattern in patterns:
        for match in re.findall(pattern, content):
            if isinstance(match, tuple):
                continue
    for match in re.finditer(r"(references|scripts|assets)/[A-Za-z0-9._/-]+", content):
        references.add(match.group(0))
    return sorted(references)


def ensure_bundle_structure(bundle_root: str, referenced_files: List[str]) -> Dict[str, List[str]]:
    created: Dict[str, List[str]] = {"directories": [], "files": []}
    os.makedirs(bundle_root, exist_ok=True)

    for rel_path in referenced_files:
        abs_path = os.path.join(bundle_root, rel_path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        if not os.path.exists(abs_path):
            placeholder = ""
            if rel_path.startswith("references/"):
                placeholder = "# Reference\n\nTODO: Add reference material.\n"
            elif rel_path.startswith("scripts/"):
                placeholder = "#!/usr/bin/env bash\n\necho \"TODO: implement script\"\n"
            elif rel_path.startswith("assets/"):
                placeholder = ""
            if placeholder:
                with open(abs_path, "w", encoding="utf-8") as f:
                    f.write(placeholder)
                created["files"].append(rel_path)
        root_dir = rel_path.split("/", 1)[0]
        if root_dir not in created["directories"]:
            created["directories"].append(root_dir)

    return created


def build_tree(root_dir: str, root_name: str) -> str:
    lines: List[str] = [f"{root_name}/"]

    def walk(current_dir: str, prefix: str) -> None:
        entries = sorted(os.listdir(current_dir))
        for i, entry in enumerate(entries):
            path = os.path.join(current_dir, entry)
            is_last = i == len(entries) - 1
            connector = "└── " if is_last else "├── "
            lines.append(f"{prefix}{connector}{entry}")
            if os.path.isdir(path):
                extension = "    " if is_last else "│   "
                walk(path, prefix + extension)

    walk(root_dir, "")
    return "\n".join(lines)
