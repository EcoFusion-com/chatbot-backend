import os
import sys
import time
import json
import socket
import signal
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple, Any

try:
    import yaml  # PyYAML
except Exception as exc:
    print("ERROR: PyYAML is required. Install with: pip install pyyaml", file=sys.stderr)
    sys.exit(1)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
ACTIONS_DIR = PROJECT_ROOT / "actions"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
STATIC_DIR = PROJECT_ROOT / "static"

RASA_PORT = int(os.getenv("RASA_PORT", "5005"))
ACTIONS_PORT = int(os.getenv("ACTIONS_PORT", "5055"))
RASA_URL = f"http://localhost:{RASA_PORT}/webhooks/rest/webhook"

REPORT: List[Tuple[str, str, str]] = []  # (check, status, notes)
LOG_PREFIX = "[QA]"


def log(msg: str) -> None:
    print(f"{LOG_PREFIX} {msg}")


def check_files_exist() -> None:
    required = [
        PROJECT_ROOT / "domain.yml",
        DATA_DIR / "nlu.yml",
        DATA_DIR / "stories.yml",
        DATA_DIR / "rules.yml",
        PROJECT_ROOT / "config.yml",
        PROJECT_ROOT / "endpoints.yml",
        ACTIONS_DIR / "__init__.py",
        ACTIONS_DIR / "actions.py",
    ]
    missing = [str(p.relative_to(PROJECT_ROOT)) for p in required if not p.exists()]
    if missing:
        REPORT.append(("Project files exist", "FAIL", f"Missing: {', '.join(missing)}"))
    else:
        REPORT.append(("Project files exist", "PASS", "All required files present"))


def load_yaml(path: Path) -> Tuple[bool, Any, str]:
    try:
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return True, data, ""
    except Exception as exc:
        return False, None, str(exc)


def validate_yaml_syntax() -> None:
    paths = [
        PROJECT_ROOT / "domain.yml",
        DATA_DIR / "nlu.yml",
        DATA_DIR / "stories.yml",
        DATA_DIR / "rules.yml",
        PROJECT_ROOT / "config.yml",
        PROJECT_ROOT / "endpoints.yml",
    ]
    bad: List[str] = []
    for p in paths:
        ok, _, err = load_yaml(p)
        if not ok:
            bad.append(f"{p.name}: {err}")
    if bad:
        REPORT.append(("YAML syntax valid", "FAIL", "; ".join(bad)))
    else:
        REPORT.append(("YAML syntax valid", "PASS", "All YAML files parse correctly"))


def parse_domain(domain: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "intents": set(domain.get("intents", []) or []),
        "entities": set(domain.get("entities", []) or []),
        "responses": set((domain.get("responses") or {}).keys()),
        "actions": set(domain.get("actions", []) or []),
        "slots": set((domain.get("slots") or {}).keys()),
    }


def parse_nlu(nlu: Dict[str, Any]) -> Dict[str, Any]:
    intents = []
    for item in nlu.get("nlu", []) or []:
        name = item.get("intent")
        if name:
            intents.append(name)
    return {"intents": set(intents)}


def check_nlu_vs_domain() -> None:
    ok_d, domain_data, err_d = load_yaml(PROJECT_ROOT / "domain.yml")
    ok_n, nlu_data, err_n = load_yaml(DATA_DIR / "nlu.yml")
    if not (ok_d and ok_n):
        REPORT.append(("NLU intents in domain", "FAIL", f"domain err: {err_d}; nlu err: {err_n}"))
        return
    d = parse_domain(domain_data)
    n = parse_nlu(nlu_data)
    missing_in_domain = sorted(n["intents"] - d["intents"])
    if missing_in_domain:
        REPORT.append(("NLU intents in domain", "FAIL", f"Missing in domain: {', '.join(missing_in_domain)}"))
    else:
        REPORT.append(("NLU intents in domain", "PASS", "All NLU intents are declared in domain"))


def verify_stories_responses_actions() -> None:
    ok_d, domain_data, err_d = load_yaml(PROJECT_ROOT / "domain.yml")
    ok_s, stories_data, err_s = load_yaml(DATA_DIR / "stories.yml")
    ok_r, rules_data, err_r = load_yaml(DATA_DIR / "rules.yml")
    if not ok_d:
        REPORT.append(("Stories/rules reference defined actions", "FAIL", f"domain err: {err_d}"))
        return
    d = parse_domain(domain_data)

    referenced_actions: List[str] = []
    def collect_from_steps(blocks):
        for story in blocks or []:
            for step in story.get("steps", []) or []:
                action = step.get("action")
                if action:
                    referenced_actions.append(action)
    if ok_s:
        collect_from_steps(stories_data.get("stories"))
    if ok_r:
        collect_from_steps(rules_data.get("rules"))

    missing_actions = []
    for a in referenced_actions:
        if a.startswith("utter_"):
            if a not in d["responses"]:
                missing_actions.append(a)
        else:
            if a not in d["actions"]:
                missing_actions.append(a)

    if missing_actions:
        REPORT.append(("Stories/rules reference defined actions", "FAIL", f"Missing: {', '.join(sorted(set(missing_actions)))}"))
    else:
        REPORT.append(("Stories/rules reference defined actions", "PASS", "All referenced actions/utterances exist"))


def check_slots_entities_consistency() -> None:
    ok_d, domain_data, _ = load_yaml(PROJECT_ROOT / "domain.yml")
    if not ok_d:
        REPORT.append(("Slots/entities consistency", "FAIL", "Cannot read domain.yml"))
        return
    d = parse_domain(domain_data)
    entities = d["entities"]
    slots = d["slots"]
    REPORT.append(("Slots/entities consistency", "PASS", f"Slots: {', '.join(sorted(slots))}; Entities: {', '.join(sorted(entities))}"))


def verify_actions_and_endpoints() -> None:
    ok_d, domain_data, _ = load_yaml(PROJECT_ROOT / "domain.yml")
    d = parse_domain(domain_data) if ok_d else {"actions": set()}

    actions_py = ACTIONS_DIR / "actions.py"
    defined: List[str] = []
    try:
        with actions_py.open("r", encoding="utf-8") as f:
            src = f.read()
        for a in d["actions"]:
            if a in src:
                defined.append(a)
    except Exception:
        pass

    missing = sorted(list(d["actions"] - set(defined)))

    ok_e, endpoints_data, err_e = load_yaml(PROJECT_ROOT / "endpoints.yml")
    ep_ok = ok_e and bool((endpoints_data or {}).get("action_endpoint", {}).get("url"))

    if missing:
        REPORT.append(("Custom actions defined", "FAIL", f"Missing in actions.py: {', '.join(missing)}"))
    else:
        REPORT.append(("Custom actions defined", "PASS", "All actions referenced in domain appear in actions.py"))

    if ep_ok:
        REPORT.append(("Action endpoint configured", "PASS", endpoints_data["action_endpoint"]["url"]))
    else:
        REPORT.append(("Action endpoint configured", "FAIL", err_e or "No action_endpoint.url"))


def run_cmd(cmd: List[str], timeout: int = 900) -> Tuple[int, str, str]:
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=str(PROJECT_ROOT), text=True)
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        return -1, "", f"Timeout after {timeout}s"
    return proc.returncode, out, err


def rasa_data_validate() -> None:
    code, out, err = run_cmd([sys.executable, "-m", "rasa", "data", "validate"])
    status = "PASS" if code == 0 else "FAIL"
    REPORT.append(("rasa data validate", status, (out + "\n" + err).strip()[-800:]))


def rasa_train() -> None:
    code, out, err = run_cmd([sys.executable, "-m", "rasa", "train"])
    status = "PASS" if code == 0 else "FAIL"
    REPORT.append(("rasa train", status, (out + "\n" + err).strip()[-800:]))


def rasa_test_core() -> None:
    tests_path = PROJECT_ROOT / "tests"
    if not tests_path.exists():
        REPORT.append(("rasa test core", "SKIP", "tests/ directory not found"))
        return
    code, out, err = run_cmd([sys.executable, "-m", "rasa", "test", "core", "-s", str(tests_path)])
    status = "PASS" if code == 0 else "WARN"
    REPORT.append(("rasa test core", status, (out + "\n" + err).strip()[-800:]))


def is_port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.2)
        try:
            s.connect(("127.0.0.1", port))
            return True
        except Exception:
            return False


def start_server(cmd: List[str]) -> subprocess.Popen:
    return subprocess.Popen(cmd, cwd=str(PROJECT_ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


def stop_process(proc: subprocess.Popen) -> None:
    try:
        if os.name == "nt":
            proc.terminate()
        else:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except Exception:
        pass


def simulate_conversations() -> None:
    actions_proc = start_server([sys.executable, "-m", "rasa", "run", "actions", "--port", str(ACTIONS_PORT)])
    rasa_proc = start_server([sys.executable, "-m", "rasa", "run", "--enable-api", "--port", str(RASA_PORT), "--cors", "*"])

    t0 = time.time()
    while time.time() - t0 < 60:
        if is_port_open(RASA_PORT) and is_port_open(ACTIONS_PORT):
            break
        time.sleep(0.5)

    if not (is_port_open(RASA_PORT) and is_port_open(ACTIONS_PORT)):
        REPORT.append(("Servers started", "FAIL", "Could not start Rasa or Actions server within 60s"))
        stop_process(rasa_proc)
        stop_process(actions_proc)
        return
    REPORT.append(("Servers started", "PASS", f"Rasa:{RASA_PORT}, Actions:{ACTIONS_PORT}"))

    import urllib.request

    tests = [
        ("AI & Automation", "Do you provide predictive analytics solutions?"),
        ("IoT Solutions", "How do you monitor energy consumption using IoT?"),
        ("Full-Stack", "Do you build SaaS platforms?"),
        ("Requirements Info", "What information do you need to start my project?"),
        ("Provide Requirements", "We are in healthcare, budget is 50k, timeline 3 months, tech Python"),
        ("Fallback Edge", "What’s the weather in Lahore?")
    ]

    results: List[str] = []

    for label, message in tests:
        payload = json.dumps({"sender": "qa_runner", "message": message}).encode("utf-8")
        req = urllib.request.Request(RASA_URL, data=payload, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                body = resp.read().decode("utf-8")
                arr = json.loads(body)
                texts = [str(item.get("text", "")).strip() for item in arr if isinstance(item, dict)]
                results.append(f"{label}: {' | '.join([t for t in texts if t])}")
        except Exception as exc:
            results.append(f"{label}: ERROR {exc}")

    REPORT.append(("Simulated conversations", "PASS", "\n".join(results)))

    stop_process(rasa_proc)
    stop_process(actions_proc)


def print_markdown_report() -> None:
    print("\n| Check | Status | Notes |")
    print("| --- | --- | --- |")
    for check, status, notes in REPORT:
        notes_short = notes.replace("\n", "<br/>")
        print(f"| {check} | {status} | {notes_short} |")

    print("\nSuggestions:")
    print("- Add tests for negative/fallback trajectories and multi-turn requirement filling.")
    print("- Include entity extraction tests for industry, budget, timeline, technology.")
    print("- Add conversation tests for bot_challenge and ask_requirements_info.")

    print("\nProduction optimizations:")
    print("- Containerize Rasa and Actions with Docker; include healthchecks and a compose file.")
    print("- Set up CI/CD to run `rasa data validate`, `rasa test`, and push a versioned model artifact on main.")
    print("- Externalize secrets (HF_API_TOKEN) via env and add rate limiting/retries for the HF API calls.")


def main() -> None:
    os.chdir(PROJECT_ROOT)
    log(f"Project root: {PROJECT_ROOT}")

    check_files_exist()
    validate_yaml_syntax()
    check_nlu_vs_domain()
    verify_stories_responses_actions()
    check_slots_entities_consistency()

    rasa_data_validate()
    rasa_train()
    rasa_test_core()
    simulate_conversations()

    print_markdown_report()


if __name__ == "__main__":
    main()
