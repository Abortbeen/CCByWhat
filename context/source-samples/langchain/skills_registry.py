"""Skills registry - manages built-in and user-defined skills."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Awaitable

logger = logging.getLogger(__name__)


@dataclass
class Skill:
    """A skill definition that can be invoked via slash command."""

    name: str
    description: str
    prompt_template: str  # The prompt text injected when skill is invoked
    aliases: list[str] = field(default_factory=list)
    allowed_tools: list[str] = field(default_factory=list)
    source: str = "builtin"  # "builtin", "user", "mcp", "plugin"

    def get_prompt(self, args: str = "") -> str:
        """Generate the prompt for this skill.

        Args:
            args: User-provided arguments after the skill name.

        Returns:
            The prompt text to inject into the conversation.
        """
        if "{args}" in self.prompt_template:
            return self.prompt_template.replace("{args}", args)
        if args:
            return f"{self.prompt_template}\n\nUser request: {args}"
        return self.prompt_template


class SkillsRegistry:
    """Registry for all available skills."""

    def __init__(self) -> None:
        self._skills: dict[str, Skill] = {}
        self._alias_map: dict[str, str] = {}

    def register(self, skill: Skill) -> None:
        """Register a skill.

        Args:
            skill: Skill definition to register.
        """
        self._skills[skill.name] = skill
        for alias in skill.aliases:
            self._alias_map[alias] = skill.name
        logger.debug("Registered skill: %s", skill.name)

    def get(self, name: str) -> Skill | None:
        """Get a skill by name or alias.

        Args:
            name: Skill name or alias.

        Returns:
            Skill instance or None.
        """
        # Direct lookup
        if name in self._skills:
            return self._skills[name]
        # Alias lookup
        real_name = self._alias_map.get(name)
        if real_name:
            return self._skills.get(real_name)
        return None

    def list_skills(self) -> list[Skill]:
        """List all registered skills.

        Returns:
            List of all skills.
        """
        return list(self._skills.values())

    def load_from_directory(self, skills_dir: Path) -> int:
        """Load user-defined skills from a directory.

        Each skill is a .md file with optional YAML frontmatter:
        ---
        name: my-skill
        description: Does something cool
        aliases: [ms]
        ---
        The rest of the file is the prompt template.

        Args:
            skills_dir: Directory containing skill .md files.

        Returns:
            Number of skills loaded.
        """
        if not skills_dir.exists():
            return 0

        loaded = 0
        for skill_file in skills_dir.glob("*.md"):
            try:
                content = skill_file.read_text(encoding="utf-8")
                skill = self._parse_skill_file(skill_file.stem, content)
                if skill:
                    self.register(skill)
                    loaded += 1
            except Exception as e:
                logger.warning("Failed to load skill %s: %s", skill_file, e)

        return loaded

    def _parse_skill_file(self, default_name: str, content: str) -> Skill | None:
        """Parse a skill from file content with optional YAML frontmatter.

        Args:
            default_name: Default name (filename without extension).
            content: File content.

        Returns:
            Parsed Skill or None.
        """
        name = default_name
        description = ""
        aliases: list[str] = []

        # Check for YAML frontmatter
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                try:
                    # Simple YAML-like parsing (no dependency)
                    frontmatter = parts[1].strip()
                    for line in frontmatter.split("\n"):
                        line = line.strip()
                        if line.startswith("name:"):
                            name = line[5:].strip().strip('"').strip("'")
                        elif line.startswith("description:"):
                            description = line[12:].strip().strip('"').strip("'")
                        elif line.startswith("aliases:"):
                            alias_str = line[8:].strip()
                            if alias_str.startswith("["):
                                aliases = [
                                    a.strip().strip('"').strip("'")
                                    for a in alias_str.strip("[]").split(",")
                                    if a.strip()
                                ]
                except Exception:
                    pass
                content = parts[2].strip()

        if not content:
            return None

        return Skill(
            name=name,
            description=description or f"Skill: {name}",
            prompt_template=content,
            aliases=aliases,
            source="user",
        )

    def load_from_config(self, skills_config: list[dict[str, Any]]) -> int:
        """Load skills from config JSON.

        Args:
            skills_config: List of skill definitions from config.

        Returns:
            Number of skills loaded.
        """
        loaded = 0
        for skill_def in skills_config:
            try:
                skill = Skill(
                    name=skill_def["name"],
                    description=skill_def.get("description", ""),
                    prompt_template=skill_def.get("prompt", ""),
                    aliases=skill_def.get("aliases", []),
                    source="config",
                )
                self.register(skill)
                loaded += 1
            except (KeyError, TypeError) as e:
                logger.warning("Invalid skill config: %s", e)

        return loaded


# Global singleton
_registry: SkillsRegistry | None = None


def get_skills_registry() -> SkillsRegistry:
    """Get or create the global skills registry.

    Returns:
        The singleton SkillsRegistry instance.
    """
    global _registry
    if _registry is None:
        _registry = SkillsRegistry()
    return _registry
