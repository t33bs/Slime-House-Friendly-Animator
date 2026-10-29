"""Static guardrails for the Windows release pipeline."""
import unittest
from pathlib import Path
from studio.release_config import APP_VERSION

ROOT = Path(__file__).resolve().parents[1]

class WindowsReleasePipelineTests(unittest.TestCase):
    def test_windows_ci_runs_packaged_exe_smoke(self):
        workflow = (ROOT / '.github/workflows/build-friendly-animator.yml').read_text()
        self.assertIn('windows-latest', workflow)
        self.assertIn('SlimeHouseFriendlyAnimator.exe', workflow)
        self.assertIn('--smoke-test', workflow)
        self.assertIn('ExitCode', workflow)

    def test_gui_smoke_checks_window_transitions_and_resources(self):
        code = (ROOT / 'friendly_animator.py').read_text()
        self.assertIn("'--smoke-test' in sys.argv", code)
        for term in ('showMinimized', 'showMaximized', 'showNormal', 'bundled_resource_report'):
            self.assertIn(term, code)

    def test_installer_version_matches_application(self):
        iss = (ROOT / 'packaging/FriendlyAnimator.iss').read_text()
        self.assertIn(f'#define AppVersion "{APP_VERSION}"', iss)
        self.assertIn('UninstallDisplayIcon', iss)
        self.assertIn('recursesubdirs', iss)

    def test_release_pipeline_builds_installer_and_portable(self):
        workflow = (ROOT / '.github/workflows/build-friendly-animator.yml').read_text()
        self.assertIn('ISCC.exe', workflow)
        self.assertIn('Windows-Portable', workflow)
        self.assertIn('Windows-Installer', workflow)

    def test_ci_installs_smokes_and_uninstalls_real_installer(self):
        workflow = (ROOT / '.github/workflows/build-friendly-animator.yml').read_text()
        for term in ('/VERYSILENT', '/DIR=', 'unins000.exe', 'Installed GUI smoke test failed',
                     'Application executable remained after uninstall', 'Installer-Diagnostics'):
            self.assertIn(term, workflow)

    def test_installer_is_per_user_and_does_not_remove_user_projects(self):
        iss = (ROOT / 'packaging/FriendlyAnimator.iss').read_text()
        self.assertIn('PrivilegesRequired=lowest', iss)
        self.assertNotIn('[UninstallDelete]', iss)

    def test_upgrade_pipeline_preserves_user_project_bytes(self):
        workflow = (ROOT / '.github/workflows/build-friendly-animator.yml').read_text()
        for term in ('Test reinstall/upgrade and preservation of user projects',
                     'foreach ($pass in 1..2)', 'WriteAllBytes($project, $original)',
                     'Get-FileHash -Algorithm SHA256 $project', 'User project changed during uninstall'):
            self.assertIn(term, workflow)

    def test_upgrade_test_exercises_installed_gui_twice(self):
        workflow = (ROOT / '.github/workflows/build-friendly-animator.yml').read_text()
        self.assertIn("GUI smoke failed after pass ${pass}", workflow)
        self.assertIn('Uninstall after upgrade failed', workflow)

    def test_smoke_checks_actual_window_states_and_resizing(self):
        code = (ROOT / 'friendly_animator.py').read_text()
        for term in ('window.isMinimized()', 'window.isMaximized()',
                     'screen.availableGeometry()', 'window.resize(',
                     '(800,600)', '(1280,720)', '(1920,1080)'):
            self.assertIn(term, code)

    def test_windows_runner_records_qt_diagnostics(self):
        workflow = (ROOT / '.github/workflows/build-friendly-animator.yml').read_text()
        self.assertIn('Record Windows display and Qt runtime diagnostics', workflow)
        self.assertIn('PySide6.__version__', workflow)

class WindowsBuildTimeoutTests(unittest.TestCase):
    def test_windows_build_and_gui_checks_have_time_limits(self):
        workflow = (ROOT / '.github/workflows/build-friendly-animator.yml').read_text()
        self.assertIn('runs-on: windows-latest\n    timeout-minutes: 45', workflow)
        for name, limit in (
            ('Test packaged GUI and offline resources on Windows', 5),
            ('Test silent install, installed GUI and uninstall on Windows', 10),
            ('Test reinstall/upgrade and preservation of user projects', 12),
        ):
            self.assertIn(f'- name: {name}\n        timeout-minutes: {limit}', workflow)

class WindowsPytestGateTests(unittest.TestCase):
    def test_windows_ci_runs_pytest_before_packaging(self):
        workflow = (ROOT / '.github/workflows/build-friendly-animator.yml').read_text()
        pytest_command = 'python -u -m pytest -vv -x --tb=short --durations=20 --timeout=120 --timeout-method=thread tests'
        self.assertIn(pytest_command, workflow)
        self.assertIn('Pytest integration regression suite failed', workflow)
        self.assertIn('FriendlyAnimator-Phase1-Windows-Pytest-Log', workflow)
        self.assertLess(workflow.index(pytest_command), workflow.index('pyinstaller --noconfirm'))
