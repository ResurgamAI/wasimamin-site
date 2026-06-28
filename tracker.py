#!/usr/bin/env python3
"""
tracker.py — Job Application Manager for wasimamin.us

Manages the job tracker directly in GitHub. No local files needed.
Run from anywhere Python is available — terminal, Google Colab, Replit, etc.

Usage:
  python3 tracker.py list
  python3 tracker.py list --status applied
  python3 tracker.py add
  python3 tracker.py update
  python3 tracker.py delete
  python3 tracker.py summary

Requirements: Python 3.7+ (stdlib only, no pip installs)

Set these once as environment variables, or paste them when prompted:
  GH_TOKEN   — GitHub personal access token (repo scope)
  GH_REPO    — ResurgamAI/wasimamin-site
  GH_FILE    — private/LRkFOQzb3fY/index.html
"""

import os, sys, json, re, base64, urllib.request, urllib.error, textwrap
from datetime import date

# ── Config ────────────────────────────────────────────────────────────────────

TOKEN   = os.environ.get("GH_TOKEN",  "")
REPO    = os.environ.get("GH_REPO",   "ResurgamAI/wasimamin-site")
FILE    = os.environ.get("GH_FILE",   "private/LRkFOQzb3fY/index.html")
API     = f"https://api.github.com/repos/{REPO}/contents/{FILE}"

STATUSES = {
    "1": ("not-applied",       "Not applied"),
    "2": ("applied",           "Applied"),
    "3": ("interview-pending", "Interview pending"),
    "4": ("interviewed",       "Interviewed"),
    "5": ("offer-received",    "Offer received"),
    "6": ("rejected-closed",   "Rejected / closed"),
}

STATUS_LABEL = {v: label for v, (v2, label) in STATUSES.items() for v in [v2]}

COLORS = {
    "not-applied":       "\033[90m",   # grey
    "applied":           "\033[94m",   # blue
    "interview-pending": "\033[93m",   # yellow
    "interviewed":       "\033[95m",   # magenta
    "offer-received":    "\033[92m",   # green
    "rejected-closed":   "\033[91m",   # red
}
RESET = "\033[0m"
BOLD  = "\033[1m"

# ── GitHub helpers ────────────────────────────────────────────────────────────

def get_token():
    global TOKEN
    if not TOKEN:
        TOKEN = input("GitHub token (ghp_...): ").strip()
    return TOKEN

def gh_get():
    """Fetch the HTML file from GitHub. Returns (content_str, sha)."""
    req = urllib.request.Request(API, headers={
        "Authorization": f"Bearer {get_token()}",
        "Accept": "application/vnd.github+json",
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
            content = base64.b64decode(data["content"]).decode("utf-8")
            return content, data["sha"]
    except urllib.error.HTTPError as e:
        print(f"GitHub error {e.code}: {e.read().decode()}")
        sys.exit(1)

def gh_put(html: str, sha: str, message: str):
    """Push updated HTML back to GitHub."""
    body = json.dumps({
        "message": message,
        "content": base64.b64encode(html.encode()).decode(),
        "sha": sha,
    }).encode()
    req = urllib.request.Request(API, data=body, headers={
        "Authorization": f"Bearer {get_token()}",
        "Content-Type": "application/json",
        "Accept": "application/vnd.github+json",
    }, method="PUT")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            result = json.loads(r.read())
            sha_new = result.get("content", {}).get("sha", "")[:8]
            print(f"\n✓ Committed to GitHub (sha {sha_new})")
            print(f"  Netlify will deploy in ~20 seconds.")
            print(f"  Live at: https://wasimamin.us/private/LRkFOQzb3fY/")
    except urllib.error.HTTPError as e:
        print(f"GitHub push error {e.code}: {e.read().decode()}")
        sys.exit(1)

# ── Parse / serialise applications in the HTML ───────────────────────────────

def parse_apps(html: str) -> list:
    """Extract the SEED array from the HTML as a list of dicts."""
    m = re.search(r"const SEED = \[(.*?)\];\s*/\* ─── State", html, re.DOTALL)
    if not m:
        # Fallback: look for SEED anywhere
        m = re.search(r"const SEED = \[(.*?)\];", html, re.DOTALL)
    if not m:
        print("ERROR: Could not find SEED array in tracker HTML.")
        sys.exit(1)
    raw = m.group(1)

    apps = []
    # Each entry is a JS object literal on one or more lines
    for entry in re.finditer(r"\{([^}]+)\}", raw, re.DOTALL):
        obj = entry.group(1)
        item = {}
        for key in ["company", "role", "status", "description", "appliedDate", "url"]:
            km = re.search(rf"{key}:\s*'([^']*)'", obj)
            if km:
                item[key] = km.group(1)
        # priority flag
        if re.search(r"priority:\s*true", obj):
            item["priority"] = True
        if item.get("company"):
            apps.append(item)
    return apps

def serialise_apps(apps: list) -> str:
    """Convert list of dicts back to JS SEED array source."""
    lines = []
    for a in apps:
        parts = []
        parts.append(f"  company: '{_esc(a.get('company',''))}'")
        if a.get("role"):
            parts.append(f"role: '{_esc(a.get('role',''))}'")
        parts.append(f"status: '{a.get('status','not-applied')}'")
        if a.get("priority"):
            parts.append("priority: true")
        if a.get("appliedDate"):
            parts.append(f"appliedDate: '{a['appliedDate']}'")
        if a.get("url"):
            parts.append(f"url: '{a['url']}'")
        if a.get("description"):
            parts.append(f"description: '{_esc(a.get('description',''))}'")
        lines.append("  { " + ", ".join(parts) + " }")
    return "const SEED = [\n" + ",\n".join(lines) + "\n];"

def _esc(s):
    return s.replace("'", "\\'")

def update_html(html: str, apps: list) -> str:
    """Replace the SEED block in the HTML with updated data."""
    new_seed = serialise_apps(apps)
    # Replace from 'const SEED = [' up to the closing '];'
    html = re.sub(
        r"const SEED = \[.*?\];",
        new_seed,
        html,
        flags=re.DOTALL,
        count=1,
    )
    return html

# ── Display ───────────────────────────────────────────────────────────────────

def print_app(idx: int, a: dict, show_idx=True):
    status = a.get("status", "not-applied")
    color  = COLORS.get(status, "")
    label  = STATUS_LABEL.get(status, status)
    pri    = " ★" if a.get("priority") else ""
    prefix = f"[{idx+1:>2}]  " if show_idx else "     "
    company = a.get("company","?")
    role    = a.get("role","") or ""
    desc    = a.get("description","") or ""
    applied = f"  · {a['appliedDate']}" if a.get("appliedDate") else ""

    print(f"{prefix}{BOLD}{company}{pri}{RESET}  —  {role}")
    print(f"       {color}{label}{RESET}{applied}")
    if desc:
        wrapped = textwrap.fill(desc, width=70, initial_indent="       ", subsequent_indent="       ")
        print(f"\033[90m{wrapped}{RESET}")

def status_menu():
    print("\n  Status options:")
    for k, (val, label) in STATUSES.items():
        print(f"    {k}) {label}")

# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_list(args):
    """List all applications, optionally filtered by status."""
    filter_status = None
    if "--status" in args:
        idx = args.index("--status")
        if idx + 1 < len(args):
            filter_status = args[idx + 1]

    print("\nFetching tracker from GitHub…")
    html, _ = gh_get()
    apps = parse_apps(html)

    if filter_status:
        apps = [a for a in apps if a.get("status") == filter_status]
        print(f"\nShowing: {STATUS_LABEL.get(filter_status, filter_status)} ({len(apps)} entries)\n")
    else:
        print(f"\nAll applications ({len(apps)} total)\n")

    if not apps:
        print("  No entries found.")
        return

    # Group by status for cleaner display
    order = [s for s, _ in STATUSES.values()]
    grouped = {}
    for a in apps:
        st = a.get("status","not-applied")
        grouped.setdefault(st, []).append(a)

    real_idx = 0
    for st_val, st_label in STATUSES.values():
        group = grouped.get(st_val, [])
        if not group:
            continue
        color = COLORS.get(st_val, "")
        print(f"{BOLD}{color}── {st_label} ({len(group)}) ──{RESET}")
        for a in group:
            print_app(real_idx, a)
            real_idx += 1
            print()

def cmd_summary(args):
    """Print a count summary by status."""
    print("\nFetching tracker from GitHub…")
    html, _ = gh_get()
    apps = parse_apps(html)

    counts = {}
    for a in apps:
        st = a.get("status","not-applied")
        counts[st] = counts.get(st, 0) + 1

    total = len(apps)
    print(f"\n  Application Summary — {total} total\n")
    for _, (st_val, st_label) in STATUSES.items():
        n = counts.get(st_val, 0)
        if n:
            bar = "█" * n
            color = COLORS.get(st_val,"")
            print(f"  {color}{st_label:<22}{RESET}  {bar}  {n}")
    print()

def cmd_add(args):
    """Add a new application interactively."""
    print("\n── Add new application ──\n")

    company = input("Company name: ").strip()
    if not company:
        print("Company name required.")
        return

    role = input("Role / position (Enter to skip): ").strip()

    status_menu()
    st_choice = input("\nStatus [1-6, default=1]: ").strip() or "1"
    status = STATUSES.get(st_choice, STATUSES["1"])[0]

    applied_date = ""
    if status in ("applied", "interview-pending", "interviewed", "offer-received"):
        d = input(f"Date applied (YYYY-MM-DD) [{date.today()}]: ").strip()
        applied_date = d if d else str(date.today())

    url = input("Job posting URL (Enter to skip): ").strip()
    description = input("Notes / description (Enter to skip): ").strip()
    priority = input("Mark as priority? [y/N]: ").strip().lower() == "y"

    new_app = {"company": company}
    if role:           new_app["role"] = role
    new_app["status"]  = status
    if priority:       new_app["priority"] = True
    if applied_date:   new_app["appliedDate"] = applied_date
    if url:            new_app["url"] = url
    if description:    new_app["description"] = description

    print("\nFetching current tracker…")
    html, sha = gh_get()
    apps = parse_apps(html)
    apps.append(new_app)

    print(f"\nAdding:  {company} — {role or '(no role)'} [{STATUS_LABEL[status]}]")
    confirm = input("Commit to GitHub? [Y/n]: ").strip().lower()
    if confirm == "n":
        print("Cancelled.")
        return

    new_html = update_html(html, apps)
    gh_put(new_html, sha, f"Add application: {company} — {role or status}")

def cmd_update(args):
    """Update status or notes on an existing application."""
    print("\nFetching tracker from GitHub…")
    html, sha = gh_get()
    apps = parse_apps(html)

    # Show compact list
    print(f"\n  {'#':<4} {'Company':<22} {'Role':<35} Status")
    print("  " + "─"*80)
    for i, a in enumerate(apps):
        status = a.get("status","not-applied")
        color  = COLORS.get(status,"")
        label  = STATUS_LABEL.get(status, status)
        role   = (a.get("role") or "")[:33]
        company = (a.get("company") or "")[:20]
        print(f"  {i+1:<4} {company:<22} {role:<35} {color}{label}{RESET}")

    print()
    choice = input("Entry number to update: ").strip()
    try:
        idx = int(choice) - 1
        assert 0 <= idx < len(apps)
    except:
        print("Invalid selection.")
        return

    app = apps[idx]
    print(f"\nEditing: {app.get('company')} — {app.get('role','')}")
    print(f"Current status: {STATUS_LABEL.get(app.get('status',''), app.get('status',''))}\n")

    print("What to update?")
    print("  1) Status")
    print("  2) Notes / description")
    print("  3) Role")
    print("  4) Applied date")
    print("  5) URL")
    print("  6) Priority flag")
    field = input("\nChoice [1-6]: ").strip()

    if field == "1":
        status_menu()
        st_choice = input("\nNew status [1-6]: ").strip()
        if st_choice in STATUSES:
            app["status"] = STATUSES[st_choice][0]
            if app["status"] in ("applied","interview-pending","interviewed","offer-received") and not app.get("appliedDate"):
                d = input(f"Applied date (YYYY-MM-DD) [{date.today()}]: ").strip()
                app["appliedDate"] = d if d else str(date.today())
    elif field == "2":
        current = app.get("description","")
        print(f"Current: {current}")
        new_desc = input("New notes (Enter to keep): ").strip()
        if new_desc:
            app["description"] = new_desc
    elif field == "3":
        print(f"Current: {app.get('role','')}")
        new_role = input("New role (Enter to keep): ").strip()
        if new_role:
            app["role"] = new_role
    elif field == "4":
        print(f"Current: {app.get('appliedDate','(none)')}")
        new_date = input("New date YYYY-MM-DD (Enter to keep): ").strip()
        if new_date:
            app["appliedDate"] = new_date
    elif field == "5":
        print(f"Current: {app.get('url','(none)')}")
        new_url = input("New URL (Enter to keep): ").strip()
        if new_url:
            app["url"] = new_url
    elif field == "6":
        current = app.get("priority", False)
        app["priority"] = not current
        print(f"Priority set to: {app['priority']}")
    else:
        print("Invalid choice.")
        return

    apps[idx] = app
    confirm = input("\nCommit to GitHub? [Y/n]: ").strip().lower()
    if confirm == "n":
        print("Cancelled.")
        return

    new_html = update_html(html, apps)
    gh_put(new_html, sha, f"Update: {app.get('company')} — {app.get('status')}")

def cmd_delete(args):
    """Remove an application from the tracker."""
    print("\nFetching tracker from GitHub…")
    html, sha = gh_get()
    apps = parse_apps(html)

    print(f"\n  {'#':<4} {'Company':<22} {'Role':<35} Status")
    print("  " + "─"*80)
    for i, a in enumerate(apps):
        status = a.get("status","not-applied")
        color  = COLORS.get(status,"")
        label  = STATUS_LABEL.get(status, status)
        role   = (a.get("role") or "")[:33]
        company = (a.get("company") or "")[:20]
        print(f"  {i+1:<4} {company:<22} {role:<35} {color}{label}{RESET}")

    print()
    choice = input("Entry number to DELETE: ").strip()
    try:
        idx = int(choice) - 1
        assert 0 <= idx < len(apps)
    except:
        print("Invalid selection.")
        return

    app = apps[idx]
    print(f"\n  ⚠️  Delete: {app.get('company')} — {app.get('role','')}")
    confirm = input("Type 'yes' to confirm: ").strip().lower()
    if confirm != "yes":
        print("Cancelled.")
        return

    apps.pop(idx)
    new_html = update_html(html, apps)
    gh_put(new_html, sha, f"Delete: {app.get('company')} — {app.get('role','')}")

# ── Entry point ───────────────────────────────────────────────────────────────

COMMANDS = {
    "list":    (cmd_list,    "List all applications (--status <status> to filter)"),
    "summary": (cmd_summary, "Count by status"),
    "add":     (cmd_add,     "Add a new application"),
    "update":  (cmd_update,  "Update status/notes on an existing entry"),
    "delete":  (cmd_delete,  "Remove an application"),
}

def usage():
    print(f"\n  {BOLD}tracker.py — Job Application Manager{RESET}\n")
    print("  Usage: python3 tracker.py <command>\n")
    for cmd, (_, desc) in COMMANDS.items():
        print(f"    {cmd:<10} {desc}")
    print()
    print("  Set GH_TOKEN env var to avoid entering it each time:")
    print('    export GH_TOKEN="ghp_..."')
    print()

if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        usage()
        sys.exit(0)

    cmd = args[0].lower()
    if cmd not in COMMANDS:
        print(f"Unknown command: {cmd}")
        usage()
        sys.exit(1)

    try:
        COMMANDS[cmd][0](args[1:])
    except KeyboardInterrupt:
        print("\n\nCancelled.")
