from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml

from archdrift.experiments.subjects import (
    SubjectRepositoryError,
    acquire_subjects_from_lock,
    create_subject_lock,
    load_subject_lock,
    verify_subjects,
)


def run_git(
    repository: Path,
    *arguments: str,
) -> str:
    result = subprocess.run(
        [
            "git",
            *arguments,
        ],
        cwd=repository,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )

    return result.stdout.strip()


def create_upstream_repository(
    root: Path,
) -> tuple[
    Path,
    str,
]:
    repository = (
        root
        / "upstream"
    )

    repository.mkdir()

    run_git(
        repository,
        "init",
    )

    run_git(
        repository,
        "config",
        "user.email",
        "architecture-drift@example.invalid",
    )

    run_git(
        repository,
        "config",
        "user.name",
        "ArchitectureDrift Test",
    )

    (
        repository
        / "README.md"
    ).write_text(
        "baseline\n",
        encoding="utf-8",
    )

    run_git(
        repository,
        "add",
        "README.md",
    )

    run_git(
        repository,
        "commit",
        "-m",
        "baseline",
    )

    commit = run_git(
        repository,
        "rev-parse",
        "HEAD",
    )

    return (
        repository,
        commit,
    )


def test_subject_lock_pins_exact_commit(
    tmp_path: Path,
) -> None:
    upstream, commit = (
        create_upstream_repository(
            tmp_path
        )
    )

    manifest_path = (
        tmp_path
        / "subjects.yaml"
    )

    lock_path = (
        tmp_path
        / "subjects.lock.yaml"
    )

    manifest_path.write_text(
        yaml.safe_dump(
            {
                "schema_version": "1.0",
                "subjects": [
                    {
                        "id": "test-system",
                        "repository": str(
                            upstream
                        ),
                        "ref": "HEAD",
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    lock = create_subject_lock(
        manifest_path=manifest_path,
        lock_path=lock_path,
    )

    assert len(
        lock.subjects
    ) == 1

    assert (
        lock.subjects[0].commit
        == commit
    )

    loaded = load_subject_lock(
        lock_path
    )

    assert loaded == lock


def test_acquisition_uses_locked_revision_after_upstream_moves(
    tmp_path: Path,
) -> None:
    upstream, locked_commit = (
        create_upstream_repository(
            tmp_path
        )
    )

    manifest_path = (
        tmp_path
        / "subjects.yaml"
    )

    lock_path = (
        tmp_path
        / "subjects.lock.yaml"
    )

    destination = (
        tmp_path
        / "subjects"
    )

    manifest_path.write_text(
        yaml.safe_dump(
            {
                "schema_version": "1.0",
                "subjects": [
                    {
                        "id": "test-system",
                        "repository": str(
                            upstream
                        ),
                        "ref": "HEAD",
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    create_subject_lock(
        manifest_path=manifest_path,
        lock_path=lock_path,
    )

    # Upstream changes after the experiment revision was locked.
    (
        upstream
        / "README.md"
    ).write_text(
        "new upstream revision\n",
        encoding="utf-8",
    )

    run_git(
        upstream,
        "add",
        "README.md",
    )

    run_git(
        upstream,
        "commit",
        "-m",
        "upstream moved",
    )

    new_commit = run_git(
        upstream,
        "rev-parse",
        "HEAD",
    )

    assert new_commit != locked_commit

    states = acquire_subjects_from_lock(
        lock_path=lock_path,
        destination_root=destination,
    )

    assert len(
        states
    ) == 1

    assert (
        states[0].commit
        == locked_commit
    )

    checkout = (
        destination
        / "test-system"
    )

    assert (
        run_git(
            checkout,
            "rev-parse",
            "HEAD",
        )
        == locked_commit
    )


def test_acquisition_refuses_dirty_subject_repository(
    tmp_path: Path,
) -> None:
    upstream, _ = (
        create_upstream_repository(
            tmp_path
        )
    )

    manifest_path = (
        tmp_path
        / "subjects.yaml"
    )

    lock_path = (
        tmp_path
        / "subjects.lock.yaml"
    )

    destination = (
        tmp_path
        / "subjects"
    )

    manifest_path.write_text(
        yaml.safe_dump(
            {
                "schema_version": "1.0",
                "subjects": [
                    {
                        "id": "test-system",
                        "repository": str(
                            upstream
                        ),
                        "ref": "HEAD",
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    create_subject_lock(
        manifest_path=manifest_path,
        lock_path=lock_path,
    )

    acquire_subjects_from_lock(
        lock_path=lock_path,
        destination_root=destination,
    )

    checkout = (
        destination
        / "test-system"
    )

    (
        checkout
        / "README.md"
    ).write_text(
        "local modification\n",
        encoding="utf-8",
    )

    with pytest.raises(
        SubjectRepositoryError,
        match="local modifications",
    ):
        acquire_subjects_from_lock(
            lock_path=lock_path,
            destination_root=destination,
        )


def test_verify_subjects_accepts_exact_clean_checkout(
    tmp_path: Path,
) -> None:
    upstream, _ = (
        create_upstream_repository(
            tmp_path
        )
    )

    manifest_path = (
        tmp_path
        / "subjects.yaml"
    )

    lock_path = (
        tmp_path
        / "subjects.lock.yaml"
    )

    destination = (
        tmp_path
        / "subjects"
    )

    manifest_path.write_text(
        yaml.safe_dump(
            {
                "schema_version": "1.0",
                "subjects": [
                    {
                        "id": "test-system",
                        "repository": str(
                            upstream
                        ),
                        "ref": "HEAD",
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    create_subject_lock(
        manifest_path=manifest_path,
        lock_path=lock_path,
    )

    acquire_subjects_from_lock(
        lock_path=lock_path,
        destination_root=destination,
    )

    lock = load_subject_lock(
        lock_path
    )

    states = verify_subjects(
        lock=lock,
        destination_root=destination,
    )

    assert len(
        states
    ) == 1

    assert states[0].clean is True