"""Crash recovery snapshots for Friendly Animator (independent of the GUI)."""
from pathlib import Path
import tempfile


def recovery_path():
    return Path(tempfile.gettempdir()) / 'slime_house_friendly_animator' / 'recovery.rig.json'


def write_recovery(model, path=None):
    """Stage and validate a snapshot before publishing; retain previous on errors."""
    import shutil
    import uuid
    path = Path(path) if path is not None else recovery_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    token = uuid.uuid4().hex
    staging = path.with_name(f'_staging_{token}.rig.json')
    staged_assets = staging.with_suffix('')
    assets = path.with_suffix('')
    backup = path.with_name(f'_backup_{token}.rig.json')
    backup_assets = backup.with_suffix('')
    try:
        model.save_project(staging)
        # Ensure that incomplete/corrupt snapshots never replace a valid recovery.
        read_recovery(staging)
        if path.exists(): path.rename(backup)
        if assets.exists(): assets.rename(backup_assets)
        try:
            staged_assets.rename(assets)
            staging.rename(path)
        except Exception:
            if path.exists(): path.unlink()
            if assets.exists(): shutil.rmtree(assets)
            if backup.exists(): backup.rename(path)
            if backup_assets.exists(): backup_assets.rename(assets)
            raise
        backup.unlink(missing_ok=True)
        shutil.rmtree(backup_assets, ignore_errors=True)
        return path
    finally:
        staging.unlink(missing_ok=True)
        shutil.rmtree(staged_assets, ignore_errors=True)


def read_recovery(path=None):
    from studio.pet_suite_model import PetSuiteModel
    path = Path(path) if path is not None else recovery_path()
    return PetSuiteModel.load_project(path)


def discard_recovery(path=None):
    import shutil
    path = Path(path) if path is not None else recovery_path()
    path.unlink(missing_ok=True)
    shutil.rmtree(path.with_suffix(''), ignore_errors=True)


def recovery_directory():
    return recovery_path().parent / 'projects'

def list_project_recoveries(directory=None):
    """Return all independent, complete recovery project files."""
    root=Path(directory) if directory is not None else recovery_directory()
    return sorted(root.glob('creature_*.rig.json')) if root.exists() else []

def write_project_recovery(model, project_id, directory=None):
    root=Path(directory) if directory is not None else recovery_directory()
    if not isinstance(project_id,int) or project_id<0:raise ValueError('Invalid project id')
    return write_recovery(model,root / f'creature_{project_id}.rig.json')

def discard_project_recovery(project_id, directory=None):
    root=Path(directory) if directory is not None else recovery_directory()
    discard_recovery(root / f'creature_{project_id}.rig.json')
