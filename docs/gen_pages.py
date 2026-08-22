"""Generate the user documentation home page from the project README."""

from pathlib import Path

import mkdocs_gen_files

PROJECT_DIR = Path(__file__).resolve().parent.parent

readme_content = (PROJECT_DIR / "README.md").read_text().replace("](docs/", "](")
with mkdocs_gen_files.open("index.md", "w") as index_file:
    index_file.write(readme_content)
