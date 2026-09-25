#!/usr/bin/env python3
"""The skills are claims about a running server. Check them against what the server documents.

Run: python tests/check_skills.py

Someone installs this plugin and their agent then believes what these files say about tool names,
endpoints, whether a key is needed and what the access terms are. Every one of those is a fact about
software that moves, and nothing at the other end knows this repository exists. That is exactly the
shape of thing that drifts for a release and is found by a user.

The oracle is `energy-flow-x/MCP.md`, which a Java test holds the server to. Checking against it makes
a tool name here transitively checked against the running service, which is the only thing that
matters to whoever installed this.

Standard library only, so the checks run wherever the repo is cloned.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PLUGIN = REPO / "plugins" / "energyflowx"
SKILLS = PLUGIN / "skills"

# The sibling checkout that documents the server. Absent outside the development workspace, which is
# the one case where skipping is right: a user who cloned this repo has no energy-flow-x beside it,
# and failing would make the checks unrunnable for exactly the people we want running them.
MCP_MD = REPO.parent / "energy-flow-x" / "MCP.md"

FAILURES: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"  ok    {name}")
    else:
        print(f"  FAIL  {name}" + (f" — {detail}" if detail else ""))
        FAILURES.append(name)


def frontmatter(skill: Path) -> dict[str, str]:
    """The YAML header, parsed just enough. No dependency for four keys."""
    text = skill.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    header = text.split("---", 2)[1]
    fields: dict[str, str] = {}
    key = None
    for line in header.splitlines():
        match = re.match(r"^([a-zA-Z-]+):\s*(.*)$", line)
        if match:
            key = match.group(1)
            fields[key] = match.group(2).strip()
        elif key and line.strip():
            fields[key] += " " + line.strip()
    return fields


def skill_dirs() -> list[Path]:
    return sorted(p for p in SKILLS.iterdir() if (p / "SKILL.md").is_file())


def test_manifests_parse() -> None:
    print("manifests")
    for path in [REPO / ".claude-plugin" / "marketplace.json",
                 PLUGIN / ".claude-plugin" / "plugin.json",
                 PLUGIN / ".mcp.json"]:
        try:
            json.loads(path.read_text(encoding="utf-8"))
            check(f"{path.relative_to(REPO)} parses", True)
        except Exception as error:  # noqa: BLE001
            check(f"{path.relative_to(REPO)} parses", False, str(error))

    marketplace = json.loads((REPO / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    plugin = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    check("the marketplace points at a plugin that exists",
          (REPO / marketplace["plugins"][0]["source"]).resolve() == PLUGIN.resolve())
    check("the marketplace and the plugin agree on the version",
          marketplace["plugins"][0]["version"] == plugin["version"],
          "a user who installs by version gets one thing and sees another")
    # Reserved by Anthropic: names that impersonate an official source are refused at submission.
    reserved = {"claude-code-marketplace", "claude-plugins-official", "anthropic-marketplace",
                "official-claude-plugins", "npm", "pip", "uv", "cargo", "github"}
    check("the marketplace name is not a reserved one", marketplace["name"] not in reserved)


def test_frontmatter_is_portable() -> None:
    print("frontmatter stays inside the Agent Skills spec")
    # Only these six survive upload to claude.ai or the Skills API. A Claude Code-only field such as
    # `context: fork` fails the upload outright, and a skill that installs in one place and not
    # another is worse than one that never claimed to be portable.
    allowed = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
    for skill in skill_dirs():
        fields = frontmatter(skill / "SKILL.md")
        extra = set(fields) - allowed
        check(f"{skill.name}: only spec fields", not extra, f"unsupported: {sorted(extra)}")
        check(f"{skill.name}: has a name and a description",
              bool(fields.get("name")) and len(fields.get("description", "")) > 80,
              "the description is the whole triggering mechanism")
        # The spec caps it at 1024 characters, and the hydronic one was 1214 before anyone measured.
        check(f"{skill.name}: description within the 1024-character cap",
              len(fields.get("description", "")) <= 1024,
              f"{len(fields.get('description', ''))} characters")


def test_tool_names_match_the_server() -> None:
    print("tool names against energy-flow-x/MCP.md")
    if not MCP_MD.is_file():
        print(f"  skip  no energy-flow-x beside this repository ({MCP_MD})")
        return

    documented = set(re.findall(r"^\| `([a-z_]+)`", MCP_MD.read_text(encoding="utf-8"), re.M))
    check("MCP.md still lists tools the way this reads it", len(documented) > 10,
          f"found {len(documented)}")

    for skill in skill_dirs():
        named = set()
        for path in skill.rglob("*.md"):
            named |= set(re.findall(r"\b(?:get|list|size|select|search|convert|calculate|hydronic)_[a-z_]+\b",
                                    path.read_text(encoding="utf-8")))
        unknown = {tool for tool in named if tool not in documented}
        check(f"{skill.name}: names no tool the server does not have", not unknown,
              f"unknown: {sorted(unknown)}")


def test_access_terms_are_stated() -> None:
    print("access terms")
    hydronic = (SKILLS / "hydronic" / "SKILL.md").read_text(encoding="utf-8").lower()
    # These terms are a commercial position and they change. A skill that says "free" without the
    # qualification gets relayed to an end user as a promise the product never made, and an agent
    # repeats it far more confidently than a web page would.
    check("hydronic says the free period is temporary",
          "free while it is being tested" in hydronic and
          ("temporary" in hydronic or "change at any time" in hydronic))
    check("hydronic says a key is required", "api key" in hydronic)

    readme = (REPO / "README.md").read_text(encoding="utf-8").lower()
    check("the README says it too, for anyone who reads no further",
          "temporary" in readme and "without notice" in readme)


def test_mcp_wiring_matches_the_published_endpoints() -> None:
    print("mcp wiring")
    servers = json.loads((PLUGIN / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]
    urls = {name: entry["url"] for name, entry in servers.items()}

    check("the free endpoint is wired",
          any(url.endswith("/energy-flow-x/mcp") for url in urls.values()))
    check("the hydronic endpoint is wired",
          any(url.endswith("/energy-flow-x/mcp/hydronic") for url in urls.values()))
    check("every endpoint is https",
          all(url.startswith("https://") for url in urls.values()),
          "an API key must never travel over http")

    keyed = [name for name, entry in servers.items() if "headers" in entry]
    check("the key rides only on the endpoint that needs one",
          len(keyed) == 1 and keyed[0].endswith("hydronic"),
          "sending a credential to the anonymous endpoint leaks it for no reason")



def test_every_documented_tool_is_covered() -> None:
    print("tool coverage")
    if not MCP_MD.is_file():
        print("  skip  no energy-flow-x beside this repository")
        return
    documented = re.findall(r"^\| `([a-z_]+)`", MCP_MD.read_text(encoding="utf-8"), re.M)
    text = "\n".join(p.read_text(encoding="utf-8") for p in SKILLS.rglob("*.md"))
    uncovered = [tool for tool in documented if tool not in text]
    # A tool the server serves and no skill mentions is a capability the user paid attention for and
    # will never be offered. The plugin claims to cover the surface; this is what makes that true.
    check(f"all {len(documented)} documented tools appear in a skill", not uncovered,
          f"uncovered: {uncovered}")


def test_the_readme_commands_actually_work() -> None:
    print("README against the manifests")
    marketplace = json.loads((REPO / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    plugin = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    readme = (REPO / "README.md").read_text(encoding="utf-8")

    # A README whose install command does not match the manifest names fails at the first thing a
    # new user types, which is the worst possible place to be wrong.
    install = f"/plugin install {plugin['name']}@{marketplace['name']}"
    check("the install command matches the manifest names", install in readme, install)

    repo_path = plugin["repository"].replace("https://github.com/", "")
    add_cmd = f"/plugin marketplace add {repo_path}"
    check("the marketplace command matches the repository field", add_cmd in readme, add_cmd)

    env_var = plugin["metadata"]["apiKeyEnvVar"]
    mcp_raw = (PLUGIN / ".mcp.json").read_text(encoding="utf-8")
    check("the API key variable is named the same in the manifest, the wiring and the README",
          env_var in mcp_raw and env_var in readme, env_var)


def test_skill_references_resolve() -> None:
    print("bundled files a skill points at")
    for skill in skill_dirs():
        text = (skill / "SKILL.md").read_text(encoding="utf-8")
        for rel in set(re.findall(r"`((?:references|scripts)/[\w.-]+)`", text)):
            # A dead pointer sends the reader nowhere and is invisible until someone follows it.
            check(f"{skill.name}: {rel}", (skill / rel).is_file(), "SKILL.md points at a missing file")


def test_capabilities_page_matches_the_server() -> None:
    print("CAPABILITIES.md against energy-flow-x/MCP.md")
    page = (REPO / "CAPABILITIES.md").read_text(encoding="utf-8")
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    check("the README links the capabilities page", "CAPABILITIES.md" in readme)
    if not MCP_MD.is_file():
        print("  skip  no energy-flow-x beside this repository")
        return
    documented = set(re.findall(r"^\| `([a-z_]+)`", MCP_MD.read_text(encoding="utf-8"), re.M))
    named = set(re.findall(r"\b(?:get|list|size|select|search|convert|calculate|hydronic)_[a-z_]+\b", page))
    # The page is the detailed promise. A tool it leaves out is a capability nobody is told about,
    # and a tool it names that the server lacks is a promise the service cannot keep.
    check("every documented tool has its section", not (documented - named),
          f"missing: {sorted(documented - named)}")
    check("it names no tool the server does not have", not (named - documented),
          f"unknown: {sorted(named - documented)}")


def main() -> int:
    for test in [test_manifests_parse,
                 test_frontmatter_is_portable,
                 test_tool_names_match_the_server,
                 test_access_terms_are_stated,
                 test_mcp_wiring_matches_the_published_endpoints,
                 test_every_documented_tool_is_covered,
                 test_the_readme_commands_actually_work,
                 test_skill_references_resolve,
                 test_capabilities_page_matches_the_server]:
        test()
    print()
    if FAILURES:
        print(f"{len(FAILURES)} failed: " + ", ".join(FAILURES))
        return 1
    print("all checks pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
