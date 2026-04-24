from __future__ import annotations

import pytest
from app.controllers.project_controller import ProjectController
from app.controllers.selection_controller import SelectionController
from app.controllers.timeline_controller import TimelineController
from app.domain.project import build_demo_project


def _build_timeline_controller() -> tuple[TimelineController, SelectionController]:
    project_controller = ProjectController()
    project_controller.set_active_project(build_demo_project())
    selection_controller = SelectionController()
    timeline_controller = TimelineController(
        project_controller=project_controller,
        selection_controller=selection_controller,
    )
    return timeline_controller, selection_controller


def test_set_snapping_enabled_affects_snap_result() -> None:
    timeline_controller, _selection_controller = _build_timeline_controller()
    timeline_controller.configure_timeline_metrics(
        pixels_per_second=90.0,
        snap_threshold_pixels=10.0,
        playhead_seconds=0.0,
        minimum_clip_duration_seconds=0.2,
    )

    project = timeline_controller.active_project()
    assert project is not None
    first_clip = project.timeline.tracks[1].clips[0]
    neighbour_clip = project.timeline.tracks[1].clips[1]
    proposed_start = neighbour_clip.timeline_start + 0.02

    snapped_start, _snapped_duration, snap_target = timeline_controller.get_snap_position(
        first_clip.clip_id,
        proposed_start,
        first_clip.duration,
        "move",
    )
    assert snap_target is not None
    assert snapped_start == pytest.approx(neighbour_clip.timeline_start, abs=0.1) or snapped_start == pytest.approx(
        neighbour_clip.timeline_end, abs=0.1
    )

    timeline_controller.set_snapping_enabled(False)
    unsnapped_start, _duration, unsnapped_target = timeline_controller.get_snap_position(
        first_clip.clip_id,
        proposed_start,
        first_clip.duration,
        "move",
    )
    assert unsnapped_target is None
    assert unsnapped_start == pytest.approx(proposed_start)


def test_add_caption_segments_creates_text_clips_and_selects_last() -> None:
    timeline_controller, selection_controller = _build_timeline_controller()
    timeline_controller.set_playhead_seconds(0.0)

    project = timeline_controller.active_project()
    assert project is not None
    text_track = project.timeline.tracks[0]
    initial_clip_count = len(text_track.clips)

    imported_count = timeline_controller.add_caption_segments(
        [
            (0.5, 1.25, "Caption one"),
            (2.0, 3.0, "Caption two"),
        ]
    )

    assert imported_count == 2
    assert len(text_track.clips) == initial_clip_count + 2
    assert selection_controller.selected_clip_id() == text_track.clips[-1].clip_id
