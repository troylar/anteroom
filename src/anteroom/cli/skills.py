"""Skill system for custom CLI commands.

Skills are YAML files in ~/.anteroom/skills/ or .anteroom/skills/ (project-level).
Each skill defines a prompt template that gets injected when invoked via /skill_name.

Example skill file (~/.anteroom/skills/commit.yaml):
    name: commit
    description: Create a git commit with a conventional message
    prompt: |
      Look at the current git diff and staged changes.
      Create a commit with a conventional commit message.
      Format: type(scope): description
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_VALID_SKILL_NAME = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
MAX_SKILLS = 100
_ARGS_PLACEHOLDER = "{args}"


@dataclass
class Skill:
    name: str
    description: str
    prompt: str
    source: str = ""  # "default", "global", or "project"


@dataclass
class _LoadResult:
    skills: list[Skill] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _yaml_error_hint(error: yaml.YAMLError) -> str:
    """Return an actionable hint for common YAML errors."""
    msg = str(error)
    if "mapping values are not allowed here" in msg:
        return "Hint: values containing colons must be quoted, or use block scalar '|' for multi-line prompts"
    if "while parsing a flow mapping" in msg or "expected ',' or '}'" in msg:
        return (
            "Hint: '{args}' is interpreted as YAML flow mapping. "
            "Use block scalar 'prompt: |' for prompts containing curly braces"
        )
    return ""


def _format_yaml_error(path: Path, error: yaml.YAMLError) -> str:
    """Format a YAML error with file location and hint."""
    parts = [f"Failed to load {path.name}"]
    if hasattr(error, "problem_mark") and error.problem_mark is not None:
        mark = error.problem_mark
        parts.append(f"line {mark.line + 1}, column {mark.column + 1}")
    parts_str = " (".join(parts) + (")" if len(parts) > 1 else "")
    msg = f"{parts_str}: {error.problem}" if hasattr(error, "problem") else f"{parts_str}: {error}"
    hint = _yaml_error_hint(error)
    if hint:
        msg = f"{msg}. {hint}"
    return msg


def _validate_skill_name(raw_name: str, stem: str) -> tuple[str, str | None]:
    """Validate and normalize a skill name.

    Returns (normalized_name, warning_or_none).
    """
    name = raw_name.strip() if raw_name else ""
    if not name:
        name = stem
    if not _VALID_SKILL_NAME.match(name):
        return "", f"Skipped {stem}.yaml: invalid skill name '{name}' (must match [a-z0-9][a-z0-9_-]*)"
    return name, None


def _load_skills_from_dir(skills_dir: Path, source: str) -> _LoadResult:
    """Load all .yaml skill files from a directory."""
    result = _LoadResult()
    if not skills_dir.is_dir():
        return result
    for path in sorted(skills_dir.glob("*.yaml")):
        try:
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if not isinstance(data, dict):
                result.warnings.append(f"Skipped {path.name}: invalid format (expected YAML mapping)")
                continue
            raw_name = data.get("name", path.stem)
            name, warning = _validate_skill_name(str(raw_name), path.stem)
            if warning:
                result.warnings.append(warning)
                continue
            prompt = data.get("prompt", "")
            if not prompt:
                result.warnings.append(f"Skipped {path.name}: missing 'prompt' field")
                continue
            description = data.get("description", "")
            result.skills.append(
                Skill(
                    name=name,
                    description=str(description),
                    prompt=str(prompt),
                    source=source,
                )
            )
        except yaml.YAMLError as e:
            result.warnings.append(_format_yaml_error(path, e))
        except Exception as e:
            result.warnings.append(f"Failed to load {path.name}: {e}")
    return result


def _skill_dirs(working_dir: str | None = None) -> list[Path]:
    """Return skill directories (global + project)."""
    from ..config import _resolve_data_dir

    data_dir = _resolve_data_dir()
    dirs = [data_dir / "skills"]
    current = Path(working_dir or os.getcwd()).resolve()
    while True:
        for dirname in (".anteroom", ".claude", ".parlor"):
            project_dir = current / dirname / "skills"
            if project_dir.is_dir():
                dirs.append(project_dir)
                return dirs
        parent = current.parent
        if parent == current:
            break
        current = parent
    return dirs


def load_skills(working_dir: str | None = None) -> _LoadResult:
    """Load skills from global and project directories."""
    combined = _LoadResult()
    dirs = _skill_dirs(working_dir)
    sources = ["global"] + ["project"] * (len(dirs) - 1)
    for d, source in zip(dirs, sources):
        result = _load_skills_from_dir(d, source)
        combined.skills.extend(result.skills)
        combined.warnings.extend(result.warnings)
    return combined


def _expand_args(prompt: str, args: str) -> str:
    """Expand {args} placeholder in prompt, or append as context."""
    if _ARGS_PLACEHOLDER in prompt:
        return prompt.replace(_ARGS_PLACEHOLDER, args)
    return f"{prompt}\n\nAdditional context: {args}"


class SkillRegistry:
    """Manages loaded skills."""

    def __init__(self) -> None:
        self._skills: dict[str, Skill] = {}
        self.load_warnings: list[str] = []

    def load(self, working_dir: str | None = None) -> None:
        """Load skills from default, global, and project directories."""
        self._skills.clear()
        self.load_warnings.clear()

        default_dir = Path(__file__).parent / "default_skills"
        default_result = _load_skills_from_dir(default_dir, "default")
        self.load_warnings.extend(default_result.warnings)
        default_names = set()
        for skill in default_result.skills:
            self._skills[skill.name] = skill
            default_names.add(skill.name)

        user_result = load_skills(working_dir)
        self.load_warnings.extend(user_result.warnings)
        for skill in user_result.skills:
            if skill.name in default_names:
                self.load_warnings.append(f"User skill '{skill.name}' ({skill.source}) overrides built-in")
            self._skills[skill.name] = skill

        if len(self._skills) > MAX_SKILLS:
            self.load_warnings.append(
                f"Loaded {len(self._skills)} skills (limit: {MAX_SKILLS}). Consider removing unused skill files."
            )

    reload = load

    def get(self, name: str) -> Skill | None:
        return self._skills.get(name)

    def list_skills(self) -> list[Skill]:
        return sorted(self._skills.values(), key=lambda s: s.name)

    def has_skill(self, name: str) -> bool:
        return name in self._skills

    def resolve_input(self, user_input: str) -> tuple[bool, str]:
        """Check if input is a skill invocation. Returns (is_skill, expanded_prompt)."""
        if not user_input.startswith("/"):
            return False, user_input
        parts = user_input.split(maxsplit=1)
        skill_name = parts[0][1:]  # Remove leading /
        skill = self._skills.get(skill_name)
        if not skill:
            return False, user_input
        args = parts[1] if len(parts) > 1 else ""
        prompt = skill.prompt
        if args:
            prompt = _expand_args(prompt, args)
        return True, prompt

    def get_skill_descriptions(self) -> list[tuple[str, str]]:
        """Return (name, description) pairs for all loaded skills, sorted by name."""
        return [(s.name, s.description) for s in self.list_skills()]

    def get_invoke_skill_definition(self) -> dict[str, Any] | None:
        """Return an OpenAI function schema for the invoke_skill tool.

        Returns None if no skills are loaded.
        """
        skills = self.list_skills()
        if not skills:
            return None
        return {
            "type": "function",
            "function": {
                "name": "invoke_skill",
                "description": (
                    "Invoke a predefined skill/workflow. Use this when the user's request "
                    "clearly matches one of the available skills listed in <available_skills>."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "skill_name": {
                            "type": "string",
                            "enum": [s.name for s in skills],
                            "description": "The name of the skill to invoke.",
                        },
                        "args": {
                            "type": "string",
                            "description": "Optional additional context or arguments for the skill.",
                        },
                    },
                    "required": ["skill_name"],
                },
            },
        }
