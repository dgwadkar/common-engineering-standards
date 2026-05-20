"""Phase 5 acceptance tests for ``compiler.transformers.memory_bank_scaffold``."""
from __future__ import annotations

import io
import json
import pathlib

from compiler.core.stack_filter import stack_by_id
from compiler.transformers import memory_bank_scaffold


def test_render_returns_all_six_canonical_filenames() -> None:
    stack = stack_by_id("java-spring-boot-3")
    content = memory_bank_scaffold.render_memory_bank(stack)
    assert set(content.keys()) == set(memory_bank_scaffold.MEMORY_BANK_FILES)
    assert len(memory_bank_scaffold.MEMORY_BANK_FILES) == 6


def test_render_team_maintained_tag_on_stubs() -> None:
    stack = stack_by_id("java-spring-boot-3")
    content = memory_bank_scaffold.render_memory_bank(stack)
    for stub in [
        memory_bank_scaffold.PROJECT_BRIEF_FILENAME,
        memory_bank_scaffold.PRODUCT_CONTEXT_FILENAME,
        memory_bank_scaffold.ACTIVE_CONTEXT_FILENAME,
        memory_bank_scaffold.PROGRESS_FILENAME,
    ]:
        assert memory_bank_scaffold.TEAM_MAINTAINED_TAG in content[stub], (
            f"Missing TEAM-MAINTAINED tag in {stub}"
        )


def test_tech_context_populated_from_meta_yaml() -> None:
    stack = stack_by_id("java-spring-boot-3")
    content = memory_bank_scaffold.render_memory_bank(stack)
    tech = content[memory_bank_scaffold.TECH_CONTEXT_FILENAME]
    assert "Spring Boot" in tech
    # Required deps from source/java/spring-boot/_meta.yml.
    assert "spring-boot-starter-web" in tech
    # Required env vars from _meta.yml.
    assert "SPRING_DATASOURCE_URL" in tech
    # Stack id appears.
    assert "java-spring-boot-3" in tech


def test_system_patterns_includes_diagram_from_meta_yaml() -> None:
    stack = stack_by_id("java-spring-boot-3")
    content = memory_bank_scaffold.render_memory_bank(stack)
    sp = content[memory_bank_scaffold.SYSTEM_PATTERNS_FILENAME]
    assert "Layered Architecture" in sp
    assert "mermaid" in sp
    assert "Layer Boundaries" in sp


def test_system_patterns_uses_fallback_diagram_when_meta_absent(tmp_path: pathlib.Path) -> None:
    """Stack without a _meta.yml uses the default layered-architecture diagram."""
    # No _meta.yml file is read in this code path because the stack catalog
    # references frameworks that have no _meta authored — we just construct a
    # stack object that points at a non-existent framework folder.
    from compiler.core.stack_filter import Stack

    fake = Stack(
        id="java-missing-1",
        language="java",
        framework="missing-framework",
        framework_version="1.0.0",
        human_name="Missing Framework 1",
    )
    content = memory_bank_scaffold.render_memory_bank(fake)
    sp = content[memory_bank_scaffold.SYSTEM_PATTERNS_FILENAME]
    assert "Layered Architecture" in sp
    assert "mermaid" in sp


def test_emit_writes_all_six_files(tmp_path: pathlib.Path) -> None:
    stack = stack_by_id("java-spring-boot-3")
    emitted = memory_bank_scaffold.emit_for_stack([], stack, dist_root=tmp_path)
    assert len(emitted) == 6
    out_dir = tmp_path / "stacks" / "java-spring-boot-3" / "memory-bank"
    for filename in memory_bank_scaffold.MEMORY_BANK_FILES:
        assert (out_dir / filename).is_file()


def test_emit_records_carry_filename_metadata(tmp_path: pathlib.Path) -> None:
    stack = stack_by_id("java-spring-boot-3")
    emitted = memory_bank_scaffold.emit_for_stack([], stack, dist_root=tmp_path)
    by_filename = {r.filename: r for r in emitted}
    for filename in memory_bank_scaffold.MEMORY_BANK_FILES:
        assert filename in by_filename
        assert by_filename[filename].bytes_written > 0


def test_emit_logs_structured_json(tmp_path: pathlib.Path) -> None:
    from compiler.core.logging_setup import get_logger

    stream = io.StringIO()
    logger = get_logger("compiler-test-mbs", stream=stream)
    memory_bank_scaffold.emit_for_stack(
        [], stack_by_id("java-spring-boot-3"), dist_root=tmp_path, logger=logger
    )
    payloads = [json.loads(ln) for ln in stream.getvalue().splitlines() if ln.strip()]
    emits = [p for p in payloads if p.get("event") == "emit" and p.get("target") == "memory_bank"]
    assert len(emits) == 6
    # Each emit log carries `memory_bank_file`.
    files_logged = {p["memory_bank_file"] for p in emits}
    assert files_logged == set(memory_bank_scaffold.MEMORY_BANK_FILES)
