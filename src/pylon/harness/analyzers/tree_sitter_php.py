from dataclasses import dataclass, field
from pathlib import Path

import tree_sitter_php as tsphp
from tree_sitter import Language, Parser


@dataclass
class PhpClass:
    name: str
    file: str
    line: int
    extends: str | None = None
    implements: list[str] = field(default_factory=list)
    methods: list[str] = field(default_factory=list)
    properties: list[str] = field(default_factory=list)


@dataclass
class PhpModel:
    name: str
    file: str
    table: str | None = None
    fillable: list[str] = field(default_factory=list)
    relationships: list[str] = field(default_factory=list)
    casts: list[str] = field(default_factory=list)


def get_parser() -> Parser:
    language = Language(tsphp.language_php())
    parser = Parser(language)
    return parser


def extract_classes(repo_path: str, subdir: str = "app") -> list[PhpClass]:
    parser = get_parser()
    classes = []
    app_dir = Path(repo_path) / subdir

    if not app_dir.exists():
        return classes

    for php_file in app_dir.rglob("*.php"):
        try:
            source = php_file.read_bytes()
        except OSError:
            continue

        tree = parser.parse(source)
        root = tree.root_node

        for node in _find_nodes(root, "class_declaration"):
            cls = _parse_class(node, source, str(php_file.relative_to(repo_path)))
            if cls:
                classes.append(cls)

    return classes


def extract_models(repo_path: str) -> list[PhpModel]:
    parser = get_parser()
    models = []
    models_dir = Path(repo_path) / "app" / "Models"

    if not models_dir.exists():
        models_dir = Path(repo_path) / "app"

    for php_file in models_dir.rglob("*.php"):
        try:
            source = php_file.read_bytes()
        except OSError:
            continue

        tree = parser.parse(source)
        root = tree.root_node

        for node in _find_nodes(root, "class_declaration"):
            model = _parse_model(node, source, str(php_file.relative_to(repo_path)))
            if model:
                models.append(model)

    return models


def _find_nodes(node, node_type: str):
    if node.type == node_type:
        yield node
    for child in node.children:
        yield from _find_nodes(child, node_type)


def _parse_class(node, source: bytes, file_path: str) -> PhpClass | None:
    name_node = node.child_by_field_name("name")
    if not name_node:
        return None

    name = source[name_node.start_byte:name_node.end_byte].decode()

    extends = None
    for child in node.children:
        if child.type == "base_clause":
            for name_child in _find_nodes(child, "name"):
                extends = source[name_child.start_byte:name_child.end_byte].decode()
                break

    implements = []
    for child in node.children:
        if child.type == "class_interface_clause":
            for name_child in _find_nodes(child, "name"):
                implements.append(source[name_child.start_byte:name_child.end_byte].decode())

    methods = []
    properties = []
    body = node.child_by_field_name("body")
    if body:
        for member in body.children:
            if member.type == "method_declaration":
                mname = member.child_by_field_name("name")
                if mname:
                    methods.append(source[mname.start_byte:mname.end_byte].decode())
            elif member.type == "property_declaration":
                for prop_name in _find_nodes(member, "variable_name"):
                    properties.append(source[prop_name.start_byte:prop_name.end_byte].decode())

    return PhpClass(
        name=name,
        file=file_path,
        line=node.start_point[0] + 1,
        extends=extends,
        implements=implements,
        methods=methods,
        properties=properties,
    )


RELATIONSHIP_METHODS = {
    "hasOne", "hasMany", "belongsTo", "belongsToMany",
    "morphTo", "morphMany", "morphOne", "morphToMany", "morphedByMany",
    "hasManyThrough", "hasOneThrough",
}


def _parse_model(node, source: bytes, file_path: str) -> PhpModel | None:
    cls = _parse_class(node, source, file_path)
    if not cls:
        return None

    text = source[node.start_byte:node.end_byte].decode()

    table = None
    fillable = []
    relationships = []
    casts = []

    import re

    table_match = re.search(r"\$table\s*=\s*['\"](\w+)['\"]", text)
    if table_match:
        table = table_match.group(1)

    fillable_match = re.search(r"\$fillable\s*=\s*\[(.*?)\]", text, re.DOTALL)
    if fillable_match:
        fillable = re.findall(r"['\"](\w+)['\"]", fillable_match.group(1))

    casts_match = re.search(r"\$casts\s*=\s*\[(.*?)\]", text, re.DOTALL)
    if casts_match:
        casts = re.findall(r"['\"](\w+)['\"]", casts_match.group(1))

    for method_name in cls.methods:
        body_match = re.search(
            rf"function\s+{re.escape(method_name)}\s*\(.*?\)\s*\{{(.*?)\}}",
            text,
            re.DOTALL,
        )
        if body_match:
            body_text = body_match.group(1)
            for rel in RELATIONSHIP_METHODS:
                if f"->{rel}(" in body_text:
                    rel_model_match = re.search(
                        rf"->{rel}\(\s*([A-Za-z\\]+)::class", body_text
                    )
                    target = rel_model_match.group(1) if rel_model_match else "?"
                    relationships.append(f"{method_name}() -> {rel}({target})")

    if not relationships and not fillable:
        return None

    return PhpModel(
        name=cls.name,
        file=file_path,
        table=table,
        fillable=fillable,
        relationships=relationships,
        casts=casts,
    )


def format_classes(classes: list[PhpClass]) -> str:
    lines = ["# Class Hierarchy", "", f"Total: {len(classes)}", ""]
    for cls in sorted(classes, key=lambda c: c.file):
        ext = f" extends {cls.extends}" if cls.extends else ""
        impl = f" implements {', '.join(cls.implements)}" if cls.implements else ""
        lines.append(f"### {cls.name}{ext}{impl}")
        lines.append(f"File: {cls.file}:{cls.line}")
        if cls.methods:
            lines.append(f"Methods: {', '.join(cls.methods)}")
        if cls.properties:
            lines.append(f"Properties: {', '.join(cls.properties)}")
        lines.append("")
    return "\n".join(lines)


def format_models(models: list[PhpModel]) -> str:
    lines = ["# Models", "", f"Total: {len(models)}", ""]
    for m in sorted(models, key=lambda x: x.name):
        lines.append(f"### {m.name}")
        lines.append(f"File: {m.file}")
        if m.table:
            lines.append(f"Table: `{m.table}`")
        if m.fillable:
            lines.append(f"Fillable: {', '.join(m.fillable)}")
        if m.relationships:
            lines.append("Relationships:")
            for r in m.relationships:
                lines.append(f"  - {r}")
        if m.casts:
            lines.append(f"Casts: {', '.join(m.casts)}")
        lines.append("")
    return "\n".join(lines)
