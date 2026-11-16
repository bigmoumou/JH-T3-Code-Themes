"""Generate the live demo pages from each theme's published CSS and English mock.

Run after updating a theme: python build_gallery.py
"""
import ast
import html
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent
THEMES = ("corsair-cove", "neon-alley", "frozen-tundra", "deep-sea", "rainy-cafe")


def build():
    output = ROOT / "demo"
    output.mkdir(exist_ok=True)
    for theme_id in THEMES:
        folder = ROOT / theme_id
        tree = ast.parse((folder / "build_theme.py").read_text(encoding="utf-8"))
        mock = next(
            ast.literal_eval(node.value)
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "MOCK" for target in node.targets)
        )
        theme = json.loads((folder / "theme.json").read_text(encoding="utf-8"))
        assert mock.count("__CSS__") == 1, theme_id
        assert "</style" not in theme["css"].lower(), theme_id
        page = mock.replace("__CSS__", theme["css"])
        title = html.escape(theme_id.replace("-", " ").title() + " · JH T3 Code Themes")
        page = re.sub(r"<title>.*?</title>", f"<title>{title}</title>", page, count=1)
        assert theme["css"] in page, theme_id
        (output / f"{theme_id}.html").write_text(page, encoding="utf-8")
        print(f"{theme_id}: published CSS preserved ({len(theme['css']):,} characters)")


if __name__ == "__main__":
    build()
