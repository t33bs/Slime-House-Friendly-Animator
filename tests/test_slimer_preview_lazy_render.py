"""Prevent expensive/obscuring floating preview generation while highlighting."""
import ast
from pathlib import Path


def test_floating_preview_generated_only_after_finish_selecting():
    tree = ast.parse((Path(__file__).resolve().parents[1] / 'friendly_animator.py').read_text())
    refresh = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == 'refresh')
    calls = [node for node in ast.walk(refresh) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'slimer_preview']
    assert calls, 'refresh must still produce the selection preview after confirmation'
    for call in calls:
        ancestors = []
        def visit(node, parents):
            if node is call:
                ancestors.extend(parents)
            for child in ast.iter_child_nodes(node):
                visit(child, parents + [node])
        visit(refresh, [])
        assert any(isinstance(a, ast.If) and 'slimer_transform_mode' in ast.unparse(a.test) for a in ancestors)


def test_right_panel_reuses_canvas_preview_without_second_transform():
    source = (Path(__file__).resolve().parents[1] / 'friendly_animator.py').read_text()
    assert 'confirmed_slimer_preview=preview' in source
    assert 'pixmap(confirmed_slimer_preview, 132)' in source
