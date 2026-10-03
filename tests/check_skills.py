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
# The repository root IS the plugin, with a one-entry marketplace beside it. The directory submission
# names a folder that must hold `.claude-plugin/plugin.json` and can never be changed afterwards, and
# the first submission named the root while the plugin sat in `plugins/energyflowx`. Nothing was
# scanned. Keep the plugin at the root.
PLUGIN = REPO
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
    check("the plugin manifest sits at the repository root, the folder the directory scans",
          (REPO / ".claude-plugin" / "plugin.json").is_file())
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
        # The spec requires the name to match the folder. A mismatch is a frontmatter the directory
        # scan may not read cleanly, and it was there for a release before anyone looked.
        check(f"{skill.name}: name matches its folder", fields.get("name") == skill.name,
              f"name: {fields.get('name')}")
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
    check("hydronic says an account is required, by sign-in", "account" in hydronic and "sign" in hydronic)

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

    # Hydronic signs in with OAuth (plan mcp-oauth, design 02 §7): the client discovers the authorization
    # server from the 401 and keeps the token. A static header would skip sign-in, and the directory requires
    # OAuth for an authenticated remote server (Policy 5.D).
    keyed = [name for name, entry in servers.items() if "headers" in entry]
    check("no endpoint carries a header: the client signs in", not keyed, f"headers on: {keyed}")
    raw = (PLUGIN / ".mcp.json").read_text(encoding="utf-8")
    variables = set(re.findall(r"\$\{([^}]+)\}", raw))
    check("the wiring reads no variable at all", not variables, f"references: {sorted(variables)}")
    plugin = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    check("the plugin asks for no credential", "userConfig" not in plugin, sorted(plugin.get("userConfig", {})))


def test_directory_listing_fields() -> None:
    print("directory listing fields")
    plugin = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    icon = plugin.get("icon", "")
    check("icon points at a file in the plugin", bool(icon) and (PLUGIN / icon).is_file(), icon)
    check("icon is an SVG or a PNG", icon.endswith((".svg", ".png")), icon)
    for field in ["privacyPolicyUrl", "termsOfServiceUrl", "documentationUrl", "supportUrl"]:
        check(f"{field} is an https URL", plugin.get(field, "").startswith("https://"),
              plugin.get(field, "missing"))
    # Anything that reads a credential from the user's machine is held by the directory, even a
    # README example, so the docs must not teach it either.
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    check("the README sets no API key environment variable",
          not re.search(r"(export|setx|\$env:)\s+\w*API_KEY", readme))
    # A bundled image shown any other way than Markdown image syntax is held for a reviewer.
    check("the README shows bundled images with Markdown syntax only",
          not re.search(r"<img[^>]+src=\"(?!https?://)", readme))



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

    check("the README says how to sign in", "/mcp" in readme and "Authenticate" in readme)
    check("the README teaches no plugin option", "/plugin configure" not in readme)


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


def test_counts_agree_with_their_lists() -> None:
    print("a number on the page agrees with the list it counts")
    page = (REPO / "CAPABILITIES.md").read_text(encoding="utf-8")
    listed = set(re.findall(r"hydronic://[a-z/-]+", page))
    claimed = re.search(r"\| Tools \| \d+ \| \d+, plus (\d+) resources \|", page)
    # The table said 6 while the list under it named 9, for three releases. A count typed by hand is the
    # first thing to drift from the list it counts.
    check("the server table's resource count matches the resources listed",
          claimed is not None and int(claimed.group(1)) == len(listed),
          f"table says {claimed.group(1) if claimed else '?'}, the page lists {len(listed)}")
    if MCP_MD.is_file():
        served = set(re.findall(r"hydronic://[a-z/-]+", MCP_MD.read_text(encoding="utf-8")))
        check("and the page lists every resource the server documents", served <= listed,
              f"missing: {sorted(served - listed)}")


# Claims that were true once and are not now. Each entry says what replaced it, because a phrase on this
# list is only ever reintroduced by someone copying an old paragraph.
RETIRED = {
    "predicted to take": "the server no longer predicts a run's length and refuses it; a run that meets "
                         "its limit returns the steps it computed, marked INCOMPLETE",
    "This run was NOT started": "same: the predictive refusal is gone",
    "over a minute": "same: the 60 s refusal is gone",
    "Retry-After` and the code": "the throttled call carries retryAfterSeconds in its JSON-RPC error data",
}


def test_no_retired_claim_is_repeated() -> None:
    print("no claim the server has retired")
    texts = {path.relative_to(REPO): path.read_text(encoding="utf-8")
             for path in [REPO / "README.md", REPO / "CAPABILITIES.md", *SKILLS.rglob("*.md")]}
    for phrase, why in RETIRED.items():
        found = [str(name) for name, text in texts.items() if phrase in text]
        check(f'nobody says "{phrase}"', not found, f"{found}: {why}")
    skill = (SKILLS / "hydronic" / "SKILL.md").read_text(encoding="utf-8")
    check("the hydronic skill says what to tell a user about an unfinished run",
          "completed: false" in skill and "INCOMPLETE" in skill and "not quote it as the outcome" in skill)


def test_the_study_symbols_are_the_builders() -> None:
    print("the study's P&ID symbols")
    scripts = SKILLS / "hydronic" / "scripts"
    sys.path.insert(0, str(scripts))
    try:
        from study_glyphs import symbol_names
        from study_symbols import SYMBOLS
    finally:
        sys.path.remove(str(scripts))
    missing = [name for name in symbol_names() if name not in SYMBOLS]
    check("every symbol the glyph map names is embedded", not missing, f"missing: {missing}")
    # The renderer must stay one script with no image files to find: the directory holds a plugin for a
    # reviewer when a script refers to bundled images.
    images = [p.name for p in scripts.rglob("*") if p.suffix.lower() in {".svg", ".png", ".jpg", ".gif", ".webp"}]
    check("no image file is bundled beside the scripts", not images, f"{images}")
    sync = REPO / "tools" / "sync_symbols.py"
    ui = REPO.parent / "energy-flow-x-ui" / "src" / "assets" / "pid"
    if not ui.is_dir():
        print(f"  skip  no energy-flow-x-ui beside this repository ({ui})")
        return
    sys.path.insert(0, str(sync.parent))
    try:
        from sync_symbols import TARGET, build
    finally:
        sys.path.remove(str(sync.parent))
    check("the embedded symbols match the builder's files", TARGET.read_text(encoding="utf-8") == build(),
          "a symbol changed in the builder: run python tools/sync_symbols.py")


def test_the_license_is_named_the_way_the_directory_reads_it() -> None:
    print("licence")
    plugin = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    license_id = plugin.get("license", "")
    # The manifest field is an SPDX identifier. A proprietary licence has none, and SPDX's form for that is a
    # LicenseRef- name pointing at the LICENSE file the directory also requires.
    check("license is an SPDX identifier or a LicenseRef", bool(re.fullmatch(r"LicenseRef-[A-Za-z0-9.-]+|[A-Za-z0-9.+-]+", license_id)),
          license_id)
    check("and the LICENSE file it refers to is in the plugin", (PLUGIN / "LICENSE").is_file())


def main() -> int:
    for test in [test_counts_agree_with_their_lists,
                 test_no_retired_claim_is_repeated,
                 test_the_study_symbols_are_the_builders,
                 test_the_license_is_named_the_way_the_directory_reads_it,
                 test_manifests_parse,
                 test_frontmatter_is_portable,
                 test_tool_names_match_the_server,
                 test_access_terms_are_stated,
                 test_mcp_wiring_matches_the_published_endpoints,
                 test_directory_listing_fields,
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
