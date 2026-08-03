"""Generate API reference pages and the documentation home page.

``PROJECT_DIR`` and ``SOURCE_CODE`` identify the repository root and package
directory used for generated reference files.
"""

from pathlib import Path

import mkdocs_gen_files

PROJECT_DIR = Path(__file__).resolve().parent.parent

SOURCE_CODE = PROJECT_DIR / "src" / "lunchmoney_mcp"

for path in sorted(SOURCE_CODE.rglob("*.py")):
    module_path = path.relative_to(PROJECT_DIR).with_suffix("")
    doc_path = path.relative_to(SOURCE_CODE).with_suffix(".md")
    full_doc_path = Path("reference", doc_path)

    parts = tuple(module_path.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
        full_doc_path = full_doc_path.with_name("index.md")
    elif parts[-1] == "__main__":
        continue

    with mkdocs_gen_files.open(full_doc_path, "w") as file:
        file.write(f"# `{parts[-1]}`\n\n::: {'.'.join(parts)}")

    mkdocs_gen_files.set_edit_path(full_doc_path, path)

readme_content = (PROJECT_DIR / "README.md").read_text()
with mkdocs_gen_files.open("index.md", "w") as index_file:
    index_file.write(readme_content)
