"""Generate/check authored #303 cell snapshots. No application or domain engine.

The review viewer chooses snapshots and pages; it never dispatches slash commands.
All data is synthetic except labelled byte events read from the retained loopback
report. ASCII cells make line budgets inspectable without claiming terminal widths.
"""

import argparse
import copy
import hashlib
import json
from pathlib import Path
import textwrap


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "docs/design/cereja-ui-ledger.html"
SIZES = ((120, 40), (80, 24), (40, 12), (32, 10))


def snapshot(name, flow, lines, *, draft="/context --root /fixture/repo", focus="composer",
             overlay=False, actions=("Help", "Exit"), selected="01", item="os", anchor=0,
             active=None, blocks=None, caret=9, selection=(3, 9), form=None, consent=None):
    return dict(name=name, flow=flow, lines=lines, draft=draft, caret=caret,
                selection=list(selection), focus=focus, overlay=overlay,
                actions=list(actions), selected=selected, item=item, anchor=anchor,
                active=active, blocks=blocks or [{"id": "01", "command": "/system", "state": "Done"}],
                form=form or {}, consent=consent, provenance="SYNTHETIC UX FIXTURE")


def corpus():
    probe = json.loads((ROOT / "benchmarks/ui_spikes/download-loopback.json").read_text())
    known = next(c for c in probe["cases"] if c["mode"] == "known")
    unknown = next(c for c in probe["cases"] if c["mode"] == "unknown")
    event = next(e for e in known["events"] if e["bytes_transferred"] == 768)
    unknown_event = next(e for e in unknown["events"] if e["bytes_transferred"] == 768)
    states = {}

    def add(key, *args, **kwargs):
        states[key] = snapshot(*args, **kwargs)

    add("initial", "Initial / no collection", "L6", [
        "Discover, inspect and run Cereja capabilities.", "Type / to discover. No automatic collection.",
        "/system  /tree  /context", "/compress  /download  /examples", "Planned UI: application not implemented."],
        draft="", caret=0, selection=(0, 0), blocks=[{"id": "home", "command": "/home", "state": "Reference"}], selected="home")
    add("slash", "Slash / highlighted suggestion", "L6", [
        "DISCOVERY 1/1", "> * /system : basic snapshot", "Enter/Tab: [Insert] | Esc: [Back]"], draft="/sys", caret=4,
        selection=(4, 4), overlay="discovery", actions=("Insert", "Back"), blocks=states["initial"]["blocks"], selected="home")
    add("inserted", "Suggestion inserted / zero jobs", "L1", [
        "Selected /system; no collection started.", "A later Enter explicitly submits validation."],
        draft="/system", caret=7, selection=(7, 7), blocks=states["initial"]["blocks"], selected="home")
    add("system-working", "System / explicit basic Load", "L1", [
        "> 01 /system | Working", "Basic / identifiers off", "OS: Loading", "CPU: Loading",
        "Memory: Loading", "Known sections only; no invented values."], active="01", actions=("Details", "Help", "Exit"))
    add("system", "System / unavailable section", "L1", [
        "> 01 /system | Done | synthetic snapshot T0", "OS: Example OS", "Python: fixture version",
        "CPU: Unavailable", "Memory: Unavailable", "GPU: Unavailable", "* OS section selected",
        "No sensitive identifiers collected."], actions=("Refresh", "Details", "Help", "Exit"))
    add("system-refresh", "System / retain previous snapshot", "L1", [
        "> 01 /system | Working: Refresh", "Prior snapshot T0 remains visible", "OS: Example OS",
        "CPU: Unavailable", "New collection pending; no percentage."], active="01", actions=("Details", "Help", "Exit"))
    states["system-actions"] = {**copy.deepcopy(states["system"]),
                                "name": "System / focus Refresh without executing", "focus": "Refresh"}
    add("system-error", "System / failed Refresh", "L1", [
        "> 01 /system | Error: refresh failed", "Prior snapshot T0 retained", "OS: Example OS",
        "CPU: Unavailable", "Retry is explicit; draft untouched."], actions=("Retry", "Details", "Help", "Exit"))
    tree_form = {"Path": "/fixture/repo", "Depth": "3", "Nodes": "candidate 5000"}
    add("tree-form", "Tree / explicit parameters", "L2", [
        "Path*: /fixture/repo", "Depth: 3 (candidate)", "Node bound: 5000 (candidate)",
        "Links displayed, never descended.", "No cwd assumed; Load validates explicit path."],
        overlay=True, focus="Path", actions=("Load", "Back", "Help"), form=tree_form)
    tree_lines = ["> 02 /tree | Done | /fixture/repo", "[-] repo", "  [-] src", "  * tools.py",
                  "  [+] tests", "  README.md", "Selected: /fixture/repo/src/tools.py", "No open/edit/delete actions."]
    add("tree", "Tree / selected nested node", "L2", tree_lines, selected="02", item="src/tools.py",
        focus="tree", anchor=2, actions=("Details", "Help", "Exit"), form=tree_form)
    add("tree-collapsed", "Tree / collapse keeps parent selection", "L2", [
        "> 02 /tree | Done", "[-] repo", "  * [+] src", "  [+] tests", "Selected: /fixture/repo/src"],
        selected="02", item="src", focus="tree", actions=("Expand", "Details", "Help", "Exit"), form=tree_form)
    add("tree-detail", "Tree / full sanitized path", "L2", [
        "Path: /fixture/repo/src/tools.py", "Kind: file", "Read-only inspection; Back restores node and anchor."],
        overlay=True, selected="02", item="src/tools.py", focus="detail", anchor=2,
        actions=("Back", "Help"), form=tree_form)
    add("tree-incomplete", "Tree / unavailable child", "L2", [
        "> 02 /tree | Warning: incomplete", "Root: /fixture/repo", "tests: permission unavailable",
        "Omitted count: unknown", "Do not infer complete traversal from clipped output."],
        selected="02", item="tests", actions=("Edit", "Details", "Help", "Exit"))
    context_form = {"Roots": "/fixture/repo;/fixture/docs", "Query": "needle", "Extensions": ".py,.md"}
    add("context-form", "Context / explicit roots and limits", "L3", [
        "Roots*: /fixture/repo; /fixture/docs", "Query*: needle", "Extensions: .py,.md",
        "Max results: 10", "Max file: 1 MiB", "Snippets/result: 2", "Chars/snippet: 240",
        "Cache: off", "Result cap is not a scan bound."], overlay=True, focus="Roots",
        actions=("Search", "Back", "Help"), form=context_form)
    add("context-invalid", "Context / validation keeps valid fields", "L3", [
        "Roots*: /fixture/repo; /fixture/docs", "Query*: [empty]", "Error: Query is required.",
        "Extensions: .py,.md", "Other values retained; zero jobs started."], overlay=True, focus="Query",
        actions=("Edit", "Back", "Help"), form={**context_form, "Query": ""})
    add("context", "Context / bounded results", "L3", [
        "> 03 /context | Done", "Roots: /fixture/repo; /fixture/docs", "Query: needle", "* src/tools.py:12",
        "  docs/guide.md:8", "Skipped: 1 oversized file", "Within limits; no cache writes."],
        selected="03", item="src/tools.py:12", focus="results", anchor=3,
        actions=("Snippet", "Edit", "Help", "Exit"), form=context_form)
    add("context-detail", "Context / literal match snippet", "L3", [
        "src/tools.py:12", "return [needle] + value", "Bounded synthetic snippet; untrusted text never executes.",
        "Back restores result identity and anchor."], overlay=True, selected="03", item="src/tools.py:12",
        focus="detail", anchor=3, actions=("Back", "Help"), form=context_form)
    add("empty", "Context / empty within bounds", "L3", [
        "> 03 /context | Empty within limits", "Roots: /fixture/repo; /fixture/docs", "Query: absent",
        "Skipped: 1 oversized file", "Not proof of no match outside these limits."], actions=("Edit", "Help", "Exit"))
    for mode in ("Compress", "Decompress"):
        for kind in ("File", "Directory"):
            key = f"archive-{mode.lower()}-{kind.lower()}"
            source = "/fixture/input/data" if mode == "Compress" else "/fixture/input/data.archive"
            target = "/fixture/output/data.archive" if mode == "Compress" else "/fixture/output/restored"
            params = {"Mode": mode, "Kind": kind, "Source": source, "Destination": target}
            add(key, f"Archive / {mode} {kind} form", "L4", [
                "Mode: " + mode, "Kind: " + kind, "Source*: " + source, "Destination*: " + target,
                "Policy: explicit tested bounds required", "Existing output: refuse", "Review before effects."],
                overlay=True, focus="Source", actions=("Review", "Back", "Help"), form=params)
    target = "/fixture/output/restored/nested/exact-directory-target"
    archive_tuple = {"action": "Decompress", "source": "/fixture/input/data.archive", "kind": "Directory",
                     "target": target, "effect": "create-new", "policy": "fixture-policy", "target_state": "absent"}
    add("archive-review", "Directory / safety stages and exact target", "L4", [
        "Action: Decompress Directory", "Source: /fixture/input/data.archive", "Exact target: " + target,
        "Effect: create new directory only", "Validate members/paths/types/links/collisions",
        "Enforce expansion/count/depth limits in owned staging", "Validate full result before publication",
        "Publish no-clobber under tested policy", "Report partial/omission/cleanup state", "No merge, deletion or Cancel."],
        overlay=True, focus="Back", actions=("Back", "Run", "Help"), form=archive_tuple, consent=archive_tuple)
    add("archive-refused", "Archive / existing target refused", "L4", [
        "Exact target: " + target, "Error: target exists; replacement unsupported", "Old destination retained",
        "No replacement action, no execution.", "Edit target invalidates previous consent."],
        overlay=True, focus="Back", actions=("Back", "Edit", "Help"), form={**archive_tuple, "target_state": "exists"})
    add("confirm", "File / conditional supported-policy confirmation", "L4", [
        "SYNTHETIC POLICY ONLY; not current service support", "Action: replace file under tested policy",
        "Source: /fixture/input/data", "Exact target: /fixture/output/data.archive",
        "Effect: replace this file only", "Target state: fixture-v1; any change invalidates",
        "Inspect full effects; recheck before publication", "Default: Keep existing. Enter activates focus only."],
        overlay=True, focus="Keep", actions=("Keep", "Replace", "Help"), consent={
            "action": "Compress", "source": "/fixture/input/data", "kind": "File", "target": "/fixture/output/data.archive",
            "effect": "replace", "policy": "synthetic-tested-policy", "target_state": "fixture-v1"})
    add("archive-rejected", "Directory / unsafe member rejected", "L4", [
        "> 04 /compress | Error: unsafe member", "Rejected: parent traversal / unsupported link",
        "Final target unchanged", "No publish; only owned staging may be cleaned", "Edit and review before retry."],
        actions=("Edit", "Details", "Help", "Exit"))
    add("archive-working", "Archive / indeterminate execution", "L4", [
        "> 04 /compress | Working", "Destination: /fixture/output/data.archive",
        "Known operation active; no percentage/speed/ETA", "No safe cooperative stop demonstrated"], active="04")
    add("archive-warning", "Archive / partial cleanup warning", "L4", [
        "> 04 /compress | Warning: cleanup incomplete", "Publication: not completed", "Final target unchanged",
        "Owned staging remains: /fixture/output/owned-stage", "Do not claim rollback or automatic retry."],
        actions=("Details", "Edit", "Help", "Exit"))
    add("archive-success", "Archive / committed outcome", "L4", [
        "> 04 /compress | Done (synthetic outcome)", "Target: /fixture/output/data.archive",
        "Publication: committed", "Owned cleanup: complete", "Omissions: none in this synthetic case"], actions=("Details", "Help", "Exit"))
    download_form = {"URL": "https://example.invalid/fixture.bin", "Destination": "/fixture/output/fixture.bin"}
    add("download-form", "Download / explicit URL and target", "L5", [
        "URL*: https://example.invalid/fixture.bin", "Destination*: /fixture/output/fixture.bin",
        "HTTP(S) only; TLS verification retained", "No headers/body editor; no resume claim",
        "Review target before network/file effects."], overlay=True, focus="URL",
        actions=("Review", "Back", "Help"), form=download_form)
    add("download-review", "Download / effects review", "L5", [
        "URL: https://example.invalid/fixture.bin", "Exact target: /fixture/output/fixture.bin",
        "Effects: network read + owned temporary output", "Existing target: refuse by default",
        "Commit after transfer; recheck target state", "No safe Cancel; unknown total stays bounded by policy"],
        overlay=True, focus="Back", actions=("Back", "Run", "Help"), form=download_form)
    for key, ev in (("download-known", event), ("download-unknown", unknown_event)):
        lines = ["> 05 /download | Working", "Captured loopback event replay, not live",
                 f"Received: {ev['bytes_transferred']} bytes"]
        if ev["total_bytes"] is not None:
            lines += [f"Total: {ev['total_bytes']} bytes", "[##########..........] 50%"]
        else:
            lines += ["Total: unknown; indeterminate activity"]
        lines += ["Speed/ETA: unavailable", "Bytes complete does not mean published"]
        add(key, "Download / captured " + ("known total" if ev["total_bytes"] else "unknown total"),
            "L5", lines, active="05", form=download_form)
        states[key]["provenance"] = "CAPTURED LOOPBACK BYTES; OTHER STATE SYNTHETIC"
    add("download-error", "Download / network error and partial state", "L5", [
        "> 05 /download | Error: network read failed", "Target: /fixture/output/fixture.bin",
        "Old target preserved (synthetic case)", "Owned partial cleanup: complete (synthetic)",
        "Retry revalidates; no resume promise."], actions=("Edit", "Retry", "Details", "Help", "Exit"), form=download_form)
    add("examples", "Examples / synthetic reference", "L6", [
        "> 06 /examples | SYNTHETIC ONLY", "* Text/table", "  Input/selection", "  Feedback/log",
        "Demonstration count: 6/20 steps", "Not service progress or cooperative-stop evidence."],
        selected="06", item="table", focus="examples", actions=("Inspect", "Help", "Exit"))
    add("catalogue", "Catalogue / honest availability", "L6", [
        "> 07 /tools | Reference", "System / Tree / Context / Archives / Download: Planned UI",
        "CLI: cereja system info; cereja tree PATH", "CLI: cereja context search --root ROOT --query QUERY",
        "CLI: cereja compress; cereja decompress; cereja download",
        "HTTP/encrypt/decrypt/protect/privacy/security/module: CLI",
        "Python API: see source-grounded operation contracts", "Unbuilt integration is never Available"], actions=("Details", "Help", "Exit"))
    add("diagnostics", "Diagnostics / session policies", "L6", [
        "Terminal capability values: fixture only", "ASCII / no-color / Motion off", "One operation; no queue",
        "Retention candidates: 20 completed + 1 active; 2 MiB", "No history in disk; no secret identifiers",
        "Export is not automatic"], actions=("Help", "Exit"))
    blocks = [{"id": "01", "command": "/system", "state": "Done"},
              {"id": "05", "command": "/download", "state": "Working"}]
    add("ledger", "Ledger / inspect earlier block while working", "shared", [
        "> * 01 /system | Done", "OS: Example OS", "Memory: Unavailable", "",
        "  05 /download | Working", "Captured bytes available in Download specimen",
        "New result; Latest is explicit", "Inspecting 1/2; follow-latest off"],
        active="05", blocks=blocks, anchor=1, focus="header", actions=("Latest", "Help", "Exit"))
    add("busy", "Second Run refused / no queue", "shared", [
        "> * 01 /system | Done", "05 /download | Working", "Working: /download; second start refused",
        "Return to current; user submits again after completion", "No deferred command was stored"],
        active="05", blocks=blocks, anchor=1, focus="header", actions=("Current", "Help", "Exit"))
    add("help", "Help / preserves edit and inspection", "L6", [
        "Context: inspected result 01; unfinished /context draft",
        "Tab: local focus; Shift+Tab: reverse", "Enter: focused action; suggestion inserts only",
        "PageUp/PageDown: selected content", "Escape: close, never cancel work",
        "Draft/caret/selection and result anchor retained"], overlay=True,
        active="05", blocks=blocks, anchor=1, focus="help", actions=("Back",))
    add("completion-help", "Completion during help / no focus steal", "shared", states["help"]["lines"],
        overlay=True, blocks=[blocks[0], {**blocks[1], "state": "Done"}],
        anchor=1, focus="help", actions=("Back",))
    add("returned", "Help closed / edited draft intact", "shared", [
        "> * 01 /system | Done", "OS: Example OS", "05 /download | Done (synthetic)",
        "New result notice; selected block 01 unchanged", "Draft/caret/selection retained"],
        blocks=states["completion-help"]["blocks"], anchor=1, focus="header", actions=("Latest", "Help", "Exit"))
    add("eviction", "Old selected block evicted / notice", "shared", [
        "Oldest completed result removed from this session", "> * 05 /download | Done",
        "Nearest surviving block selected", "Candidate caps only; no measured heap guarantee"],
        blocks=[{"id": "05", "command": "/download", "state": "Done"}], selected="05", item="none",
        focus="header", actions=("Help", "Exit"))
    add("exit", "Exit with active work / safe default", "shared", [
        "Working: /download", "Default: Stay", "Wait then exit keeps input responsive",
        "No proven cooperative Cancel", "Terminal restoration does not mean rollback"],
        overlay=True, active="05", blocks=blocks, anchor=1, focus="Stay", actions=("Stay", "Wait", "Help"))

    # These are independently authored expected copy payloads, not a clipboard API.
    markdown = '## Notes\n\nA Markdown hard break.  \nNext line.\n\n- item\n\n```python\n    value = "two  spaces"\n```\n'
    code = 'def preserve(value):\n    if value:\n        return "two  spaces"\n\n    return None\n'
    tabs = 'def tab_indent():\n\treturn "value"\n'
    selected_line = '        return "two  spaces"\n'
    selected_start = code.index(selected_line)
    copy_blocks = [{"id": "03", "command": "/context", "state": "Done"}, blocks[1]]
    for key, title, fmt, source, region, expected in (
        ("copy-markdown", "Markdown / clean source copy", "Markdown", markdown, (0, len(markdown)), markdown),
        ("copy-code", "Code / indentation and blank lines", "code", code, (0, len(code)), code),
        ("copy-tabs", "Code / preserve source tabs", "code", tabs, (0, len(tabs)), tabs),
        ("copy-range", "Selected text / logical range only", "code", code,
         (selected_start, selected_start + len(selected_line)), selected_line),
    ):
        add(key, title, "L6", [
            "> 03 /context | selected retained snippet", "SYNTHETIC COPY EXPECTATION; no clipboard write",
            "Ctrl+C: copy active text, never exit/cancel", "Source " + fmt + ":", *source.splitlines(),
            "No terminal margins/soft wraps/ANSI in payload"], selected="03", item="snippet", anchor=2,
            focus="detail", active="05", blocks=copy_blocks, actions=("Copy", "Help", "Exit"))
        states[key]["copy"] = dict(source_id="fixture/snippet", revision=1, format=fmt, source=source,
                                   logical_range=list(region), plain_text=expected, selection_active=True,
                                   ctrl_c="Copy", outcome="Ready", clipboard_ack=False,
                                   scope="Selected retained text; synthetic expected payload only")
    states["copy-failed"] = copy.deepcopy(states["copy-code"])
    states["copy-failed"]["name"] = "Copy failed / preserve selection and work"
    states["copy-failed"]["lines"] = [
        "Error: clipboard write denied (synthetic)", "No Copied claim; no fall-through to exit",
        "Text/selection/focus/inspection and job preserved", "Retry copy explicitly; payload stays inspectable"]
    states["copy-failed"]["copy"]["outcome"] = "Failed"
    states["copy-unavailable"] = copy.deepcopy(states["copy-failed"])
    states["copy-unavailable"]["name"] = "Clipboard unavailable / native fallback limit"
    states["copy-unavailable"]["lines"] = [
        "Copy unavailable on this host (synthetic)", "No automatic remote clipboard write",
        "Native emulator copy may include screen padding", "Canonical text remains inspectable; no exit"]
    states["copy-unavailable"]["copy"]["outcome"] = "Unavailable"
    states["copy-completed"] = copy.deepcopy(states["copy-code"])
    states["copy-completed"]["name"] = "Completion during selection / pinned text"
    states["copy-completed"]["active"] = None
    states["copy-completed"]["blocks"][1]["state"] = "Done"
    states["copy-completed"]["lines"] += ["New completion does not replace the selected source revision"]
    states["copy-row"] = copy.deepcopy(states["copy-code"])
    states["copy-row"]["name"] = "Selected row / explicit Copy content"
    states["copy-row"]["focus"] = "header"
    states["copy-row"]["lines"] = [
        "Selected row is navigation, not a textual range", "Explicit Copy content uses retained source",
        "Ctrl+C without active text selection follows Exit", "Clipboard transport is not implemented"]
    states["copy-row"]["copy"].update(selection_active=False, ctrl_c="Exit", scope="Explicit Copy content only")

    walks = [
        dict(name="L1 discovery and explicit load", steps=["initial", "slash", "inserted", "system-working", "system"], keys=["type /sys", "Enter inserts", "Enter submits", "domain completion"]),
        dict(name="L1 refresh failure", steps=["system", "system-actions", "system-refresh", "system-error"], keys=["Tab to Refresh, no execution", "Enter Refresh", "domain error"]),
        dict(name="L2 explicit path, details, return", steps=["tree-form", "tree", "tree-detail", "tree"], keys=["Load", "Enter details", "Escape"]),
        dict(name="L3 validation and snippet return", steps=["context-invalid", "context-form", "context", "context-detail", "context", "empty"], keys=["edit Query", "Search", "Enter snippet", "Escape", "explicit new query"]),
        dict(name="L4 modes and safety boundaries", steps=["archive-compress-file", "archive-decompress-file", "archive-compress-directory", "archive-decompress-directory", "archive-review", "archive-refused", "confirm", "archive-rejected", "archive-working", "archive-warning", "archive-success"], keys=["review independent mode" for _ in range(10)]),
        dict(name="L5 actual captured bytes and error recovery", steps=["download-form", "download-review", "download-known", "download-unknown", "download-error", "download-form"], keys=["Review", "Run in planned app", "independent unknown-total case", "synthetic failure case", "Edit"]),
        dict(name="L6 reference surfaces", steps=["examples", "catalogue", "diagnostics"], keys=["review catalogue", "review diagnostics"]),
        dict(name="One job, help, completion, return", steps=["ledger", "busy", "help", "completion-help", "returned", "eviction", "exit"], keys=["second Run refused", "Help", "domain completion", "Escape", "independent eviction case", "independent active-exit case"]),
        dict(name="Compact form and size recovery", steps=["context-form", "context-form", "context-form"], keys=["resize below minimum", "resize back"]),
        dict(name="Clean copy / source, selection and failure", steps=["copy-markdown", "copy-code", "copy-tabs", "copy-range", "copy-failed", "copy-unavailable", "copy-completed", "copy-row"],
             keys=["independent code fixture", "independent tab fixture", "select logical range", "synthetic denied-copy case", "independent unavailable-host case", "completion during selection", "independent row-navigation case"]),
    ]
    return states, walks


def wrapped(lines, width):
    result = []
    for line in lines:
        result.extend(textwrap.wrap(line, width, replace_whitespace=False,
                                    drop_whitespace=False, break_on_hyphens=False) or [""])
    return result


def frame(state, width, height, page=0):
    """Fixed review-sheet regions, not a layout/widget API."""
    cells = [[" "] * width for _ in range(height)]
    occupied = set()

    def put(y, x, text):
        assert 0 <= y < height and 0 <= x and x + len(text) <= width - 1
        assert text.isascii(), "These specimens use ASCII cells only"
        for offset, char in enumerate(text):
            coord = (y, x + offset)
            assert coord not in occupied, "Allocated regions overlap"
            occupied.add(coord)
            cells[y][x + offset] = char

    if width < 40 or height < 12:
        recovery = wrapped(["SIZE RECOVERY", f"Current {width}x{height}; need 40x12",
                            "Resize to restore editing/inspection.",
                            "Exit: Ctrl+C uses job-aware Stay/Wait.",
                            "Working: " + (state["active"] or "none"), "State retained; no auto-submit."], width - 2)
        for y, line in enumerate(recovery[:height]):
            put(y, 1, line)
        return {"cells": ["".join(r) for r in cells], "pages": 1, "body": recovery,
                "visible": recovery[:height], "actions": ["Resize", "Exit"], "recovery": True}

    put(0, 1, "CEREJA | UX REVIEW FIXTURE")
    put(1, 1, "-" * (width - 2))
    body_top, pager_y, dock_y = 3, height - 5, height - 4
    body_height = height - 8
    discovery = state["overlay"] == "discovery"
    capacity = 3 if discovery else body_height - 2 if state["overlay"] else body_height
    content = wrapped(state["lines"], width - 4)
    pages = max(1, (len(content) + capacity - 1) // capacity)
    page = min(max(page, 0), pages - 1)
    visible = content[page * capacity:(page + 1) * capacity]
    actions = " ".join("[" + a + "]" for a in state["actions"])
    if discovery:
        start = pager_y - 3
    elif state["overlay"]:
        # Short title is intentionally separate from the full review-sheet label.
        put(body_top, 2, state["flow"] + " | OVERLAY")
        put(pager_y - 1, 2, actions)
        start = body_top + 1
    else:
        start = body_top
    for y, line in enumerate(visible, start):
        put(y, 2, line)
    pager = f"Page {page + 1}/{pages} | " + ("Tab: actions" if state["overlay"] else "Tab: header/actions")
    put(pager_y, 2, pager)
    put(dock_y, 1, "-" * (width - 2))
    available = width - 9
    caret = min(state["caret"], len(state["draft"]))
    offset = max(0, caret - available + 1)
    draft = state["draft"][offset:offset + available]
    put(dock_y + 1, 2, ("cj > " if state["focus"] == "composer" else "cj : ") + draft)
    hint = "Esc: Back | Tab: focus | Help" if state["overlay"] else (
        ("> " if state["focus"] == state["actions"][0] else "") +
        f"[{state['actions'][0]}] 1/{len(state['actions'])} | Tab | Help")
    put(dock_y + 2, 2, hint)
    put(dock_y + 3, 2, "Working: " + (state["active"] or "none") + " | no queue")
    return {"cells": ["".join(r) for r in cells], "pages": pages, "body": content,
            "visible": visible, "actions": state["actions"], "recovery": False,
            "input_row": dock_y + 1, "pager_row": pager_y, "capacity": capacity}


def verify(states, walks):
    count = 0
    for state in states.values():
        before = copy.deepcopy(state)
        for width, height in SIZES:
            first = frame(state, width, height)
            all_lines = []
            for p in range(first["pages"]):
                f = frame(state, width, height, p)
                assert len(f["cells"]) == height
                assert all(len(row) == width and row[-1] == " " for row in f["cells"])
                if not f["recovery"]:
                    assert f["input_row"] == height - 3 and f["pager_row"] == height - 5
                    assert "cj " in f["cells"][height - 3]
                    assert "Page " in f["cells"][height - 5]
                    if state["overlay"]:
                        for action in state["actions"]:
                            assert "[" + action + "]" in f["cells"][height - 6]
                    else:
                        assert "[" + state["actions"][0] + "]" in f["cells"][height - 2]
                    all_lines.extend(f["visible"])
                count += 1
            if not first["recovery"]:
                assert all_lines == first["body"], "Every full value must be reachable through paging"
            assert state == before, "Rendering/resize must not mutate authored state"
    # Expectations describe authored transitions, not execution of an app engine.
    stable = ("draft", "caret", "selection", "selected", "item", "anchor")
    for field in stable:
        assert states["ledger"][field] == states["help"][field] == states["completion-help"][field] == states["returned"][field]
    assert states["completion-help"]["focus"] == "help"
    assert states["returned"]["focus"] == states["ledger"]["focus"]
    for left, right in (("tree", "tree-detail"), ("context", "context-detail")):
        for field in stable:
            assert states[left][field] == states[right][field]
    assert states["slash"]["active"] is None and states["inserted"]["active"] is None
    assert frame(states["slash"], 40, 12)["pages"] == 1
    assert states["slash"]["blocks"] == states["inserted"]["blocks"]
    assert states["busy"]["active"] == states["ledger"]["active"]
    assert states["busy"]["blocks"] == states["ledger"]["blocks"]
    assert states["archive-refused"]["consent"] is None
    assert states["archive-review"]["consent"]["target"] == states["archive-review"]["form"]["target"]
    assert states["confirm"]["focus"] == "Keep"
    assert all("Cancel" not in s["actions"] for s in states.values())
    assert all(s["provenance"] for s in states.values())
    copy_cases = [s for s in states.values() if "copy" in s]
    for s in copy_cases:
        c = s["copy"]
        start, end = c["logical_range"]
        assert c["source"][start:end] == c["plain_text"]
        assert "\x1b" not in c["plain_text"]
        assert not c["clipboard_ack"], "Viewer never acknowledges a real clipboard write"
        assert c["ctrl_c"] == ("Copy" if c["selection_active"] else "Exit")
        assert all(c["plain_text"] != "\n".join(frame(s, w, h)["cells"]) for w, h in SIZES)
    assert 'hard break.  \n' in states["copy-markdown"]["copy"]["plain_text"]
    assert '        return "two  spaces"\n\n' in states["copy-code"]["copy"]["plain_text"]
    assert '\n\treturn ' in states["copy-tabs"]["copy"]["plain_text"]
    assert states["copy-range"]["copy"]["plain_text"] == '        return "two  spaces"\n'
    for other in ("copy-failed", "copy-unavailable", "copy-completed"):
        for field in stable + ("focus",):
            assert states["copy-code"][field] == states[other][field]
        for field in ("source_id", "revision", "source", "logical_range", "plain_text"):
            assert states["copy-code"]["copy"][field] == states[other]["copy"][field]
    for walk in walks:
        assert len(walk["keys"]) == len(walk["steps"]) - 1
        assert all(key in states for key in walk["steps"])
    return {"states": len(states), "walkthroughs": len(walks), "frames_and_pages": count,
            "sizes": [list(s) for s in SIZES], "copy_expectations": len(copy_cases), "result": "passed",
            "scope": "Authored ASCII geometry/paging/actions/state continuity only; no app/terminal/user test"}


def document(states, walks):
    data = {"states": states, "walks": walks, "sizes": [], "frames": {}}
    for width, height in SIZES:
        size = f"{width}x{height}"
        data["sizes"].append(size)
        data["frames"][size] = {key: [frame(s, width, height, p)["cells"]
                                      for p in range(frame(s, width, height)["pages"])] for key, s in states.items()}
    payload = json.dumps(data, ensure_ascii=True, separators=(",", ":")).replace("<", "\\u003c")
    return TEMPLATE.replace("__DATA__", payload)


TEMPLATE = '''<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Cereja Ledger UX #303 review</title>
<style>
body{margin:0;background:#f2eee9;color:#30252b;font:16px/1.5 system-ui}main{max-width:1280px;margin:auto;padding:24px}
h1{font-size:24px;margin:0}p{max-width:85ch}label{display:inline-block;margin:8px 16px 8px 0}select,button{font:inherit;padding:5px}
button{margin:4px}a{color:#7b2042}.scroll{overflow:auto}.terminal{display:inline-block;background:#18141a;color:#e9e1e5;padding:0;font:14px/20px Consolas,'Liberation Mono',monospace}
.row{white-space:pre;height:20px}.row.heading,.row.dock{color:#ff89aa}.row.pager{font-weight:bold}.terminal.light{background:#fafafa;color:#202020}.terminal.light .heading,.terminal.light .dock{color:#004b87}
.draft-selected{text-decoration:underline;font-weight:bold}.draft-caret{box-shadow:inset 1px 0 currentColor}
.terminal.mono{background:#000;color:#fff}.terminal.mono .row{color:inherit}.terminal.c16{background:#000;color:#fff}.terminal.c16 .heading,.terminal.c16 .dock{color:#f0f}.terminal.c256{background:#1c1c1c;color:#d7d7d7}.terminal.c256 .heading,.terminal.c256 .dock{color:#ff87af}
details{margin:12px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:13px/1.5 Consolas,monospace}.notice{border-left:3px solid #9c264c;padding-left:12px}#description{min-height:3em}
#copyPayload{white-space:pre;overflow:auto;overflow-wrap:normal;background:#fff;padding:12px}
</style><main>
<h1>Ledger: cells, flows and return state</h1>
<p class="notice">Review-only authored snapshots for #303. No commands execute. All domain values, paths and outcomes are synthetic except labelled captured loopback byte events. No production widgets or application are implemented.</p>
<p><a href="cereja-ui-ux.md#final-ledger-review-contract-303">Specification</a> | <a href="cereja-ui-visual-review.md#ledger-ux-303-review-2026-10-09">Evidence and pending review</a></p>
<label>Walkthrough <select id="walk"></select></label><label>Step <select id="step"></select></label>
<label>Cells <select id="size"></select></label><label>Palette <select id="palette"><option value="">Ledger dark</option><option value="light">Light candidate</option><option value="c256">256 candidate</option><option value="c16">16 candidate</option><option value="mono">No color / ASCII</option></select></label>
<div><button id="previous">Previous specimen</button><button id="next">Next specimen</button><button id="pageBack">Previous content page</button><button id="pageNext">Next content page</button></div>
<p id="description" aria-live="polite"></p><div class="scroll"><div class="terminal" id="terminal" role="img" aria-label="Authored ASCII terminal-cell snapshot"></div></div>
<p id="provenance"></p>
<section id="copyReview" hidden><h2>Expected canonical plain text</h2><p id="copyScope"></p><pre id="copyPayload"></pre><p>Source-bound copy expectation, not reconstructed screen cells. Original Markdown/code spaces and newlines are preserved. This viewer never reads or writes your clipboard.</p></section>
<details open><summary>Independent editing / inspection / overlay state</summary><pre id="state"></pre></details>
<p>Viewer controls are external to the terminal. Tab reaches these controls; Next specimen replays an authored step, not a real key event. Motion is always off. No timers advance progress, no network/filesystem calls and no session persistence. Below-minimum recovery retains the authored state.</p>
<p>These snapshots support geometry and copy review. Terminal glyphs, key routing, responsiveness, retention memory, screen readers, usability and human acceptance require later evidence.</p>
</main><script>
'use strict';
const data=__DATA__;
const el=id=>document.getElementById(id);let currentPage=0;
function option(select,value,label){const o=document.createElement('option');o.value=value;o.textContent=label;select.append(o);}
data.walks.forEach((w,i)=>option(el('walk'),i,w.name));data.sizes.forEach(s=>option(el('size'),s,s));el('size').value='80x24';
function steps(){el('step').replaceChildren();data.walks[+el('walk').value].steps.forEach((key,i)=>option(el('step'),i,(i+1)+'. '+data.states[key].name));currentPage=0;draw();}
function draw(){const w=data.walks[+el('walk').value], index=+el('step').value, key=w.steps[index], state=data.states[key], size=el('size').value;
 const pages=data.frames[size][key];currentPage=Math.min(currentPage,pages.length-1);const rows=pages[currentPage];const h=rows.length;
 const host=el('terminal');host.replaceChildren();host.className='terminal '+el('palette').value;
 rows.forEach((text,y)=>{const row=document.createElement('div');row.className='row'+(y===0?' heading':y===h-4?' dock':y===h-5?' pager':'');
 if(y===h-3 && size!=='32x10'){const width=text.length,offset=Math.max(0,Math.min(state.caret,state.draft.length)-(width-9)+1);Array.from(text).forEach((ch,x)=>{const span=document.createElement('span');span.textContent=ch;const pos=x-7+offset;if(x>=7&&pos>=state.selection[0]&&pos<state.selection[1])span.classList.add('draft-selected');if(x>=7&&pos===state.caret&&state.focus==='composer')span.classList.add('draft-caret');row.append(span);});}else row.textContent=text;
 row.dataset.cells=text.length;host.append(row);});
 el('description').textContent=state.name+' | content page '+(currentPage+1)+'/'+pages.length+(index? ' | Authored transition: '+w.keys[index-1]:' | Start specimen');
 el('provenance').textContent=state.provenance+' | ASCII cells | Motion off';el('state').textContent=JSON.stringify(state,null,2);
 el('copyReview').hidden=!state.copy;el('copyPayload').textContent=state.copy?state.copy.plain_text:'';el('copyScope').textContent=state.copy?state.copy.scope+' | '+state.copy.outcome+' | Ctrl+C: '+state.copy.ctrl_c:'';
 el('previous').disabled=index===0;el('next').disabled=index===w.steps.length-1;el('pageBack').disabled=currentPage===0;el('pageNext').disabled=currentPage===pages.length-1;
}
el('walk').onchange=steps;el('step').onchange=()=>{currentPage=0;draw();};el('size').onchange=()=>{currentPage=0;draw();};el('palette').onchange=draw;
el('previous').onclick=()=>{el('step').value=+el('step').value-1;currentPage=0;draw();};el('next').onclick=()=>{el('step').value=+el('step').value+1;currentPage=0;draw();};
el('pageBack').onclick=()=>{currentPage--;draw();};el('pageNext').onclick=()=>{currentPage++;draw();};steps();
</script></html>
'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Verify authored requirements and generated HTML freshness")
    args = parser.parse_args()
    states, walks = corpus()
    report = verify(states, walks)
    rendered = document(states, walks)
    if args.check:
        assert OUTPUT.read_text(encoding="utf-8") == rendered, "Regenerate stale review artifact"
    else:
        OUTPUT.write_text(rendered, encoding="utf-8", newline="\n")
    report["html_sha256"] = hashlib.sha256(rendered.encode()).hexdigest()
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
