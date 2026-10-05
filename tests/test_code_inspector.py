from pathlib import Path

from reportgen.infrastructure.code_inspector import analyze, summary_text


def make_project(root: Path) -> None:
    (root / "config").mkdir()
    (root / "config" / "config.js").write_text("module.exports = {};", encoding="utf-8")
    (root / "migrations").mkdir()
    (root / "migrations" / "001-create-users.js").write_text("// migration", encoding="utf-8")
    (root / "coverage" / "lcov-report").mkdir(parents=True)
    (root / "coverage" / "lcov-report" / "index.html").write_text("<html></html>", encoding="utf-8")
    (root / "node_modules" / "pkg").mkdir(parents=True)
    (root / "node_modules" / "pkg" / "index.js").write_text("x", encoding="utf-8")
    (root / "package.json").write_text('{"dependencies": {"express": "^4"}}', encoding="utf-8")


def test_summary_lists_real_file_names_by_folder(tmp_path: Path):
    make_project(tmp_path)
    summary = summary_text(analyze(tmp_path))
    assert "Файлы в config/: config.js" in summary
    assert "Файлы в migrations/: 001-create-users.js" in summary


def test_generated_and_vendored_folders_are_ignored(tmp_path: Path):
    make_project(tmp_path)
    info = analyze(tmp_path)
    assert "HTML" not in info["languages"]
    assert info["languages"] == {"JavaScript": 2}
    assert info["dependencies"] == ["express"]
