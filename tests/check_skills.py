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


def test_every_client_manifest_agrees() -> None:
    print("client manifests: Claude, Gemini CLI and OpenAI")
    # One repository, one manifest per client, read by different crawlers. Each listing shows its own
    # manifest's words, so a manifest that lags shows an old version or a blank description somewhere
    # nobody here looks. Claude reads only .claude-plugin/, Gemini CLI only gemini-extension.json.
    plugin = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    entry = json.loads((REPO / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))["plugins"][0]
    gemini = json.loads((REPO / "gemini-extension.json").read_text(encoding="utf-8"))

    check("Gemini CLI's manifest has the plugin's name and version",
          (gemini.get("name"), gemini.get("version")) == (plugin["name"], plugin["version"]),
          f"{gemini.get('name')} {gemini.get('version')}")
    for label, manifest in [("plugin", plugin), ("marketplace entry", entry), ("Gemini CLI", gemini)]:
        check(f"the {label} manifest has a description a listing can show",
              len(manifest.get("description", "")) >= 80, manifest.get("description", "missing"))
    check("the plugin and its marketplace entry carry the same keywords",
          bool(plugin.get("keywords")) and plugin.get("keywords") == entry.get("keywords"))

    # Gemini CLI names a Streamable HTTP server `httpUrl` (`url` is its SSE transport) and signs in with OAuth
    # discovered from the 401, as Claude does. Same rules as .mcp.json: the members server, no header, no variable.
    servers = gemini.get("mcpServers", {})
    check("Gemini CLI wires the members server, over Streamable HTTP",
          [entry.get("httpUrl") for entry in servers.values()]
          == ["https://energyflowx.com/energy-flow-x/mcp/members"], str(servers))
    raw = (REPO / "gemini-extension.json").read_text(encoding="utf-8")
    check("Gemini CLI's wiring carries no header and reads no variable",
          "headers" not in raw and "${" not in raw and "settings" not in gemini)

    # OpenAI (ChatGPT and Codex) reads .codex-plugin/plugin.json, whose presentation fields sit under `interface`,
    # and its own server file: Codex names a remote server by `url` alone, where Claude's .mcp.json needs
    # `type: http`, so the two cannot share one file.
    codex = json.loads((REPO / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    face = codex.get("interface", {})
    check("the OpenAI manifest has the plugin's name, version, description and keywords",
          [codex.get(k) for k in ["name", "version", "description", "keywords"]]
          == [plugin[k] for k in ["name", "version", "description", "keywords"]])
    check("the OpenAI display name fits its 30 characters", 0 < len(face.get("displayName", "")) <= 30,
          face.get("displayName", "missing"))
    for field in ["shortDescription", "longDescription", "developerName", "category"]:
        check(f"the OpenAI listing has {field}", bool(face.get(field)), field)
    # OpenAI refuses the upload without `capabilities`, a list drawn from these three words (found 2026-10-06; Codex
    # installed the package without it, so only the dashboard catches it). The Hydronic tools build and change
    # networks and write reports on the server, so Write belongs in it alongside Read.
    capabilities = face.get("capabilities")
    check("the OpenAI listing declares its capabilities as a list of OpenAI's words",
          isinstance(capabilities, list) and bool(capabilities)
          and all(c in {"Interactive", "Read", "Write"} for c in capabilities), str(capabilities))
    check("the OpenAI capabilities say the plugin reads and writes",
          isinstance(capabilities, list) and {"Read", "Write"} <= set(capabilities), str(capabilities))
    pairs = {"websiteURL": "documentationUrl", "supportURL": "supportUrl",
             "privacyPolicyURL": "privacyPolicyUrl", "termsOfServiceURL": "termsOfServiceUrl"}
    check("the OpenAI listing links the same pages as the Claude one",
          all(face.get(theirs) == plugin.get(ours) for theirs, ours in pairs.items()),
          str({k: face.get(k) for k in pairs}))
    for field in ["logo", "composerIcon"]:
        path = face.get(field, "")
        check(f"the OpenAI {field} is a file in the plugin", bool(path) and (REPO / path).is_file(), path)
    check("the OpenAI manifest reads the shared skills", codex.get("skills") == "./skills/")
    # The review OpenAI requires for an MCP plugin: exactly five cases it should handle and three it should not, each
    # naming only tools the server really has. A case naming a renamed tool sends a reviewer looking for nothing.
    review = codex.get("extensions", {}).get("com.openai", {}).get("review", {})
    cases = review.get("test_cases", {})
    positive, negative = cases.get("positive", []), cases.get("negative", [])
    check("the OpenAI review has exactly 5 positive and 3 negative cases", (len(positive), len(negative)) == (5, 3),
          f"{len(positive)} positive, {len(negative)} negative")
    check("every positive case states its description, prompt, tools and expected behaviour",
          all(case.get(k) for case in positive for k in ["description", "prompt", "tools_triggered",
                                                           "expected_behavior"]))
    check("every negative case states its description and prompt",
          all(case.get("description") and case.get("prompt") for case in negative))
    check("the review declares no commerce", review.get("commerce") is False)
    if MCP_MD.is_file():
        served = set(re.findall(r"^\| `([a-z_]+)`", MCP_MD.read_text(encoding="utf-8"), re.M))
        named = {tool.strip() for case in positive for tool in case.get("tools_triggered", "").split(",")}
        check("every tool a review case names is one the server documents", named <= served,
              f"unknown: {sorted(named - served)}")

    wiring = REPO / codex.get("mcpServers", "missing")
    codex_servers = json.loads(wiring.read_text(encoding="utf-8"))["mcpServers"] if wiring.is_file() else {}
    check("OpenAI wires the members server by url, with no header",
          [entry.get("url") for entry in codex_servers.values()]
          == ["https://energyflowx.com/energy-flow-x/mcp/members"]
          and not any("headers" in entry for entry in codex_servers.values()), str(codex_servers))


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
    check("hydronic says the network tools are free while in testing and will become part of a paid plan",
          "free while in testing" in hydronic and "paid energyflowx plan" in hydronic)
    # The skill is read in the chat, where app directories keep selling out: OpenAI's rules let a plugin serve a
    # paid account but not display plans or promote upgrades. So it states the fact and links the terms, and the
    # year and the conditions stay on the page and in the README, for people.
    check("hydronic links the access terms instead of quoting a year or a price",
          "energyflowx.com/mcp-server" in hydronic and re.search(r"paid plan in 20\d\d|€|\$\d", hydronic) is None)
    # One year everywhere the plugin states it to a reader: a year changed in one file and not the other tells
    # two readers two different dates.
    years = {}
    for path in [PLUGIN / "README.md", PLUGIN / "CAPABILITIES.md"]:
        years[path.name] = set(re.findall(r"paid plan in (20\d\d)", path.read_text(encoding="utf-8")))
    check("every file names the same paid-plan year", len(set().union(*years.values())) == 1
          and all(years.values()), years)
    check("hydronic says an account is required, by sign-in", "account" in hydronic and "sign" in hydronic)

    readme = (REPO / "README.md").read_text(encoding="utf-8").lower()
    check("the README says it too, for anyone who reads no further",
          "free for testing" in readme and "without notice" in readme)


def test_mcp_wiring_matches_the_published_endpoints() -> None:
    print("mcp wiring")
    servers = json.loads((PLUGIN / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]
    urls = {name: entry["url"] for name, entry in servers.items()}

    # One server since 2.0.0: the members server carries every tool behind one sign-in, so a user who signed in
    # never needs an API key, and connecting the free server too would list every free tool twice.
    check("exactly one server is wired, the members server",
          list(urls.values()) == ["https://energyflowx.com/energy-flow-x/mcp/members"], str(urls))
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


# What only the plugin's own wiring, or an address that no longer exists, would make true. A skill is also
# downloaded on its own and used in assistants that never installed this plugin, so it names tools and the two
# servers by role and address, never by a name the plugin happened to give a connection.
NOT_PORTABLE = {
    "energy-flow-x-hydronic": "a plugin connection name from before 2.0.0",
    "energy-flow-x-keyed": "a connection name the old README suggested",
    "/mcp/hydronic": "an address removed on 2026-10-04",
    # The address, not Claude Code's /mcp command, which a skill may show as one client's example.
    "`/mcp` endpoint": "an address removed on 2026-10-04",
    "`/mcp` address": "an address removed on 2026-10-04",
    "`/mcp` is a separate server": "an address removed on 2026-10-04",
    "plugin server name": "a column that only makes sense with the plugin installed",
    "Hydronic MCP": "a separate server's name, gone since 2.0.0: the Hydronic tools are on the members server",
    "the plugin connects": "a claim about the plugin, which a downloaded skill does not have",
}


def test_skills_are_portable() -> None:
    for skill in skill_dirs():
        files = [skill / "SKILL.md", *sorted((skill / "references").glob("*.md"))]
        for path in files:
            text = path.read_text(encoding="utf-8")
            found = [f"{phrase} ({why})" for phrase, why in NOT_PORTABLE.items() if phrase in text]
            check(f"{skill.name}/{path.name}: reads correctly without the plugin", not found, "; ".join(found))


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
    "render_study": "the study is made on the server by hydronic_report, and the plugin ships no renderer",
    "study JSON": "same: nothing is transcribed by hand any more",
    "bundled renderer": "same: the plugin ships no renderer",
    "all four hydronic tools": "there are six: hydronic_report and hydronic_preview joined them",
    "all five hydronic tools": "there are six: hydronic_preview joined them",
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


def test_the_report_is_made_on_the_server() -> None:
    print("the study is the server's, and the plugin runs no code")
    # The study page, its diagram and its DXF were once rendered by Python scripts the assistant ran on the
    # user's machine, from a study JSON it transcribed by hand. hydronic_report makes all of it on the server
    # from the engine's own numbers, so a plugin that still shipped a renderer would offer the user a second,
    # worse path and a Python installation to manage.
    code = [str(path.relative_to(REPO)) for path in REPO.rglob("*.py")
            if ".git" not in path.parts and path.parent.name != "tests"]
    check("no script ships in the plugin", not code, f"{code}")
    skill = (SKILLS / "hydronic" / "SKILL.md").read_text(encoding="utf-8")
    check("the hydronic skill hands a study over with hydronic_report", "hydronic_report(" in skill)
    # A design built from a user's sketch is first seen as the engine read it on the report, after the solve is
    # paid for, unless the skill previews it before solving.
    loop = skill[skill.index("## The loop"):skill.index("## Reading the answer")]
    check("the hydronic skill previews the drawing before it solves",
          "hydronic_preview(" in loop and loop.index("hydronic_preview(") < loop.index("hydronic_solve("))
    report = " ".join((SKILLS / "hydronic" / "references" / "report.md").read_text(encoding="utf-8").split())
    check("its report reference says what a link is and how long it lasts",
          "anyone holding one can open the report" in report and "24 hours" in report)


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
                 test_the_report_is_made_on_the_server,
                 test_the_license_is_named_the_way_the_directory_reads_it,
                 test_manifests_parse,
                 test_every_client_manifest_agrees,
                 test_frontmatter_is_portable,
                 test_skills_are_portable,
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
