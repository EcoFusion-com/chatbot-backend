import os
import sys
import time
import json
import random
import socket
import signal
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple, Dict, Any

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RASA_PORT = int(os.getenv("RASA_PORT", "5005"))
ACTIONS_PORT = int(os.getenv("ACTIONS_PORT", "5055"))
RASA_URL = f"http://localhost:{RASA_PORT}"
REST_URL = f"{RASA_URL}/webhooks/rest/webhook"
TRACKER_URL_TMPL = f"{RASA_URL}/conversations/{{sender_id}}/tracker"

random.seed()

@dataclass
class ConvResult:
    sender_id: str
    passed: bool
    notes: List[str]
    intents_flagged: List[str]
    entities_flagged: List[str]


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


def _rest_healthcheck() -> bool:
    try:
        # lightweight probe: send a greet; if Rasa responds array -> healthy
        r = requests.post(REST_URL, json={"sender": "healthcheck", "message": "hello"}, timeout=3)
        return r.ok and isinstance(r.json(), list)
    except Exception:
        return False


def ensure_servers() -> Tuple[subprocess.Popen | None, subprocess.Popen | None, List[str]]:
    logs: List[str] = []
    actions_proc = None
    rasa_proc = None

    if not is_port_open(ACTIONS_PORT):
        actions_proc = start_server([sys.executable, "-m", "rasa", "run", "actions", "--port", str(ACTIONS_PORT)])
        logs.append("Started actions server")
    else:
        logs.append("Actions server already running")

    if not is_port_open(RASA_PORT):
        rasa_proc = start_server([sys.executable, "-m", "rasa", "run", "--enable-api", "--port", str(RASA_PORT), "--cors", "*"])
        logs.append("Started Rasa server")
    else:
        logs.append("Rasa server already running")

    # Wait up to 120s for both ports or REST healthcheck
    deadline = time.time() + 120
    while time.time() < deadline:
        ports_ok = is_port_open(RASA_PORT) and is_port_open(ACTIONS_PORT)
        if ports_ok and _rest_healthcheck():
            break
        time.sleep(0.5)

    if not _rest_healthcheck():
        # If servers are user-managed and REST is still not ready, hint to start manually
        raise RuntimeError("Servers not ready within 120s. Ensure 'rasa run --enable-api' and 'rasa run actions' are running.")

    return rasa_proc, actions_proc, logs


def send(sender: str, message: str) -> List[Dict[str, Any]]:
    resp = requests.post(REST_URL, json={"sender": sender, "message": message}, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, list) else []


def get_tracker(sender: str) -> Dict[str, Any]:
    resp = requests.get(TRACKER_URL_TMPL.format(sender_id=sender), timeout=10)
    resp.raise_for_status()
    return resp.json()


AI_QUESTIONS = [
    "Do you provide predictive analytics solutions?",
    "Can you build a chatbot for my website?",
    "Can you automate my data entry tasks?",
]
IOT_QUESTIONS = [
    "How do you monitor energy consumption using IoT?",
    "Do you offer predictive maintenance for IoT?",
    "Can you build IoT dashboards for real-time analytics?",
]
FULLSTACK_QUESTIONS = [
    "Do you build SaaS platforms?",
    "How do you handle API integrations?",
    "Do you work with Django or MERN?",
]
QUOTE_QUESTIONS = [
    "I need a quote for my project",
    "What would this cost?",
    "How much would this project cost?",
    "Give me a price estimate",
]
MEETING_QUESTIONS = [
    "I want to book a meeting",
    "Schedule a consultation",
    "Book a call",
    "Schedule a meeting",
]
HANDOFF_QUESTIONS = [
    "I need to speak with a human",
    "Transfer me to a human agent",
    "Can I talk to a real person?",
    "I want to speak to someone",
]
EDGE_QUESTIONS = [
    "What's the weather in Lahore?",
    "qwerty uiop",
    "Tell me a joke about databases",
]

REQUIREMENT_TEMPLATES = [
    "Our industry is {industry}",
    "budget is {budget}",
    "timeline {timeline}",
    "technology {technology}",
    "Project size is {project_size}",
    "Compliance requirements are {compliance}",
]

REQ_VALUES = [
    {"industry": "healthcare", "budget": "50k", "timeline": "3 months", "technology": "Python", "project_size": "medium", "compliance": "standard"},
    {"industry": "ecommerce", "budget": "20000", "timeline": "Q4", "technology": "React", "project_size": "small", "compliance": "none"},
    {"industry": "manufacturing", "budget": "100k", "timeline": "2 months", "technology": "RPA", "project_size": "large", "compliance": "strict"},
]

EXPECTED_SNIPPETS = {
    "AI": ["AI & Automation", "chatbots", "predictive"],
    "IoT": ["IoT", "energy", "sensors", "dashboards"],
    "Full": ["full-stack", "SaaS", "APIs", "cloud"],
    "ReqInfo": ["industry, budget, timeline, and preferred technology"],
    "Confirm": ["I captured your project details", "Industry:", "Consultation"],
    "Link": ["calendar.google.com"],
    "Quote": ["Estimated Cost", "Based on your requirements", "quote"],
    "Meeting": ["booking link", "consultation", "schedule"],
    "Handoff": ["human agent", "connect you with our team", "agent will be with you"],
}


def assert_contains_any(texts: List[str], expected_terms: List[str]) -> bool:
    blob = " ".join(texts).lower()
    return any(term.lower() in blob for term in expected_terms)


def human_like_flow(sender: str) -> Tuple[bool, List[str], List[str], List[str]]:
    notes: List[str] = []
    intents_flagged: List[str] = []
    entities_flagged: List[str] = []
    passed = True

    send(sender, "hello")

    # Randomly choose conversation flow
    flow_type = random.choice(["service", "quote", "meeting", "handoff"])
    
    if flow_type == "service":
        topic_choice = random.choice([("AI", AI_QUESTIONS), ("IoT", IOT_QUESTIONS), ("Full", FULLSTACK_QUESTIONS)])
        label, questions = topic_choice
        texts = [r.get("text", "") for r in send(sender, random.choice(questions))]
        notes.append(f"Service topic -> Bot: {' | '.join([t for t in texts if t])}")
        if not assert_contains_any(texts, EXPECTED_SNIPPETS[label]):
            passed = False
            intents_flagged.append({"AI": "ask_ai_automation", "IoT": "ask_iot_solutions", "Full": "ask_fullstack_dev"}[label])
    
    elif flow_type == "quote":
        texts = [r.get("text", "") for r in send(sender, random.choice(QUOTE_QUESTIONS))]
        notes.append(f"Quote request -> Bot: {' | '.join([t for t in texts if t])}")
        if not assert_contains_any(texts, EXPECTED_SNIPPETS["Quote"]):
            passed = False
            intents_flagged.append("ask_quote")
    
    elif flow_type == "meeting":
        texts = [r.get("text", "") for r in send(sender, random.choice(MEETING_QUESTIONS))]
        notes.append(f"Meeting request -> Bot: {' | '.join([t for t in texts if t])}")
        if not assert_contains_any(texts, EXPECTED_SNIPPETS["Meeting"]):
            passed = False
            intents_flagged.append("book_meeting")
    
    elif flow_type == "handoff":
        texts = [r.get("text", "") for r in send(sender, random.choice(HANDOFF_QUESTIONS))]
        notes.append(f"Handoff request -> Bot: {' | '.join([t for t in texts if t])}")
        if not assert_contains_any(texts, EXPECTED_SNIPPETS["Handoff"]):
            passed = False
            intents_flagged.append("handoff_request")

    # Requirements collection (if not handoff)
    if flow_type != "handoff":
        texts = [r.get("text", "") for r in send(sender, "What information do you need to start my project?")]
        notes.append(f"Req info -> Bot: {' | '.join([t for t in texts if t])}")
        if not assert_contains_any(texts, EXPECTED_SNIPPETS["ReqInfo"]):
            passed = False
            intents_flagged.append("ask_requirements_info")

        values = random.choice(REQ_VALUES)
        steps = random.randint(3, 6)  # Include new fields
        fields = ["industry", "budget", "timeline", "technology", "project_size", "compliance"]
        random.shuffle(fields)
        for field in fields[:steps]:
            msg = random.choice([t for t in REQUIREMENT_TEMPLATES if field in t]).format(**values)
            rtxt = [r.get("text", "") for r in send(sender, msg)]
            notes.append(f"Provide {field} -> Bot: {' | '.join([t for t in rtxt if t])}")

    # Edge case testing
    if random.random() < 0.4:
        edge = random.choice(EDGE_QUESTIONS)
        rtxt = [r.get("text", "") for r in send(sender, edge)]
        notes.append(f"Edge -> Bot: {' | '.join([t for t in rtxt if t])}")
        if len(rtxt) == 0:
            passed = False
            intents_flagged.append("fallback")

    # Final validation
    if flow_type != "handoff":
        final_msg = f"Here are my full details: industry {values['industry']}, budget {values['budget']}, timeline {values['timeline']}, technology {values['technology']}"
        final_texts = [r.get("text", "") for r in send(sender, final_msg)]
        notes.append(f"Finalize -> Bot: {' | '.join([t for t in final_texts if t])}")
        if not (assert_contains_any(final_texts, EXPECTED_SNIPPETS["Confirm"]) or assert_contains_any(final_texts, EXPECTED_SNIPPETS["Link"])):
            passed = False
            notes.append("Expectation not met: confirmation or link not found")

    # Slot validation
    tracker = get_tracker(sender)
    slots = (tracker.get("slots") or {}) if isinstance(tracker, dict) else {}
    required_slots = ["industry", "budget", "timeline", "technology"]
    if flow_type != "handoff":
        slot_ok = all(slots.get(k) for k in required_slots)
        if not slot_ok:
            passed = False
            entities_flagged.append("missing_slots")
            notes.append(f"Slots: {json.dumps(slots, ensure_ascii=False)}")

    return passed, notes, list(set(intents_flagged)), list(set(entities_flagged))


def run_one_conversation(idx: int) -> ConvResult:
    sender = f"test_user_{int(time.time())}_{idx}_{random.randint(1000,9999)}"
    passed, notes, intents_flagged, entities_flagged = human_like_flow(sender)
    return ConvResult(sender, passed, notes, intents_flagged, entities_flagged)


def main() -> None:
    rasa_proc = actions_proc = None
    try:
        rasa_proc, actions_proc, logs = ensure_servers()
        print("\n".join(["[TEST] " + l for l in logs]))

        runs = int(os.getenv("DYNAMIC_TEST_RUNS", "3"))
        results: List[ConvResult] = []
        for i in range(runs):
            res = run_one_conversation(i)
            results.append(res)

        print("\n=== Conversation Test Summary ===")
        print(f"Total runs: {len(results)}")
        for i, r in enumerate(results, 1):
            status = "PASS" if r.passed else "FAIL"
            print(f"#{i} sender={r.sender_id} -> {status}")
            if not r.passed:
                if r.intents_flagged:
                    print(f"  Intent issues: {', '.join(r.intents_flagged)}")
                if r.entities_flagged:
                    print(f"  Entity/slot issues: {', '.join(r.entities_flagged)}")
            for line in r.notes[-8:]:
                print(f"  {line}")

        failed = sum(1 for r in results if not r.passed)
        sys.exit(1 if failed else 0)

    finally:
        if rasa_proc is not None:
            stop_process(rasa_proc)
        if actions_proc is not None:
            stop_process(actions_proc)


if __name__ == "__main__":
    main()
