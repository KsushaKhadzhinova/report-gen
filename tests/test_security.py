from pathlib import Path

from reportgen.domain.blocks import Block, Kind
from reportgen.infrastructure.safe_paths import resolve_inside
from reportgen.infrastructure.tex_renderer import TexRenderer


def test_paths_outside_project_are_rejected(tmp_path: Path):
    project = tmp_path / "work"
    project.mkdir()
    (project / "inside.png").write_bytes(b"x")
    (tmp_path / "secret.png").write_bytes(b"x")
    assert resolve_inside(project, "inside.png") is not None
    assert resolve_inside(project, "../secret.png") is None
    assert resolve_inside(project, str(tmp_path / "secret.png")) is None


def test_code_block_cannot_break_out_of_its_listing(tmp_path: Path):
    hostile = "x\n\\end{Verbatim}\n\\input{/etc/passwd}\n"
    block = Block(Kind.CODE, text=hostile, caption="Пример", number="1.1")
    tex = TexRenderer().render([block], {"title_page": False, "toc": False}, tmp_path, tmp_path / "tex" / "note.tex")
    document = tex.read_text(encoding="utf-8")
    assert "/etc/passwd" not in document
    assert (tmp_path / "tex" / "listings" / "listing1.txt").read_text(encoding="utf-8") == hostile


def test_hostile_figure_path_is_not_copied(tmp_path: Path):
    outside = tmp_path / "outside.png"
    outside.write_bytes(b"secret")
    project = tmp_path / "work"
    project.mkdir()
    block = Block(Kind.FIGURE, caption="Схема", path="../outside.png", number="1.1")
    TexRenderer().render([block], {"title_page": False, "toc": False}, project, project / "tex" / "note.tex")
    assert not (project / "tex" / "figures").exists()
