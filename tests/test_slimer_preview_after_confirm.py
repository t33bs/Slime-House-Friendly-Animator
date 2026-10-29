from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1].joinpath('friendly_animator.py').read_text()


def test_preview_waits_for_finish_selecting():
    assert 'self.canvas.slimer_transform_mode and self.slimer_selection is not None' in SOURCE
    assert "self.slimer_preview_label.setText('Finish Selecting to show preview'" in SOURCE


def test_floating_result_not_drawn_during_highlighting():
    assert 'if self.canvas.slimer_transform_mode:\n                preview=self.slimer_preview()' in SOURCE
    assert '                composed.alpha_composite(preview)' in SOURCE
    assert 'if not self.canvas.slimer_transform_mode:composed.alpha_composite(tint)' in SOURCE
