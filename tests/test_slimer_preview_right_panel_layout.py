"""Regression checks for the requested UI placement and preset reference removal."""
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / 'friendly_animator.py'


def test_slimer_preview_is_added_to_right_panel_only():
    source = SOURCE.read_text(encoding='utf-8')
    assert "rl.addWidget(self.slimer_preview_label)" in source
    assert "ll.addWidget(self.slimer_preview_label)" not in source
    assert source.index("self.slimer_preview_label=QLabel") < source.index("rl.addWidget(self.slimer_preview_label)")


def test_preset_reference_removed_but_user_reference_kept():
    source = SOURCE.read_text(encoding='utf-8')
    assert "Show optional 2D pixel animation reference" not in source
    assert "self.reference_body=" not in source
    assert "self.desired=" not in source
    assert "reference_frame(" not in source
    assert "self.uploaded_reference_toggle=QCheckBox('Show my animation reference')" in source
    assert "self.uploaded_reference_image=QLabel" in source
