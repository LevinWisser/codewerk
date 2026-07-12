from __future__ import annotations


def migrate_shared_files(progress: dict, current_mission_id: str) -> None:
    """Move legacy per-mission helper files into the tutorial-wide library."""
    projects = progress.setdefault("projects", {})
    shared = dict(progress.get("shared_files", {}))
    ordered_ids = [current_mission_id, *[mission_id for mission_id in projects if mission_id != current_mission_id]]
    for mission_id in ordered_ids:
        project = projects.get(mission_id, {})
        for filename, source in project.items():
            if filename != "main.py":
                shared.setdefault(filename, source)
        if "main.py" in project:
            projects[mission_id] = {"main.py": project["main.py"]}
    progress["shared_files"] = shared


def load_mission_project(progress: dict, mission_id: str, starter_code: str) -> dict[str, str]:
    project = progress.setdefault("projects", {}).get(mission_id, {})
    main_source = project.get("main.py", starter_code)
    return {"main.py": main_source, **progress.setdefault("shared_files", {})}


def store_mission_project(progress: dict, mission_id: str, files: dict[str, str]) -> None:
    progress.setdefault("projects", {})[mission_id] = {"main.py": files.get("main.py", "")}
    progress["shared_files"] = {filename: source for filename, source in files.items() if filename != "main.py"}
