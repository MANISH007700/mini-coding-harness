import logging
from pathlib import Path

from manish_code import config

# Set up logging for this module
logger = logging.getLogger(__name__)

# Project skills ship in this folder; personal ones live in ~/.manish-code/skills.
# A user skill with the same name overrides the project one.
SKILL_DIRS = [Path(__file__).parent, config.HOME / "skills"]


def parse_skill(skill_file):
    """Split a SKILL.md into its frontmatter fields and its body."""
    logger.debug("Parsing skill file: %s", skill_file)
    text = skill_file.read_text()
    meta = {}
    if text.startswith("---"):
        _, header, text = text.split("---", 2)
        for line in header.strip().splitlines():
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()
    return meta, text.strip()


def find_skills():
    """Find every <skill dir>/<name>/SKILL.md."""
    logger.info("Scanning for skills in directories: %s", SKILL_DIRS)
    skills = {}
    for skill_file in (f for d in SKILL_DIRS for f in sorted(d.glob("*/SKILL.md"))):
        meta, _ = parse_skill(skill_file)
        name = meta.get("name", skill_file.parent.name)
        skills[name] = {"description": meta.get("description", ""), "path": skill_file}
    logger.info("Found and loaded %d skills: %s", len(skills), list(skills.keys()))
    return skills


SKILLS = find_skills()


def skills_prompt():
    """One line per skill, for telling the model what is available."""
    prompt = "\n".join(f"- {name}: {s['description']}" for name, s in SKILLS.items())
    logger.info("Generated skills prompt with %d skills.", len(SKILLS))
    return prompt


def read_skill(name: str) -> str:
    """Return a skill's full instructions."""
    logger.info("Request to read skill: '%s'", name)
    if name not in SKILLS:
        warning_msg = f"No skill named '{name}'. Available: {', '.join(SKILLS) or 'none'}"
        logger.warning(warning_msg)
        return warning_msg
    _, body = parse_skill(SKILLS[name]["path"])
    logger.info("Successfully read skill: '%s'", name)
    return body


if __name__ == "__main__":
    # If run directly, configure simple console logging so output is visible
    logging.basicConfig(level=logging.INFO)
    print(skills_prompt())
