#!/usr/bin/env python3
"""Meldet neue Events (und frei gewordene Plätze) von book.volleyballfriends.de per ntfy."""
import json
import os
import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

URL = "https://book.volleyballfriends.de/events/upcoming/"
STATE_FILE = Path("state.json")
NTFY_TOPIC = os.environ.get("NTFY_TOPIC")
NOTIFY_FREED_SPOTS = True  # auch melden, wenn ein volles Event wieder Plätze hat

ID_RE = re.compile(r"/events/([A-Z0-9]{6,})/")


def fetch_events():
    r = requests.get(URL, timeout=30, headers={"User-Agent": "event-watcher/1.0"})
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    events = {}
    for a in soup.find_all("a", href=True):
        m = ID_RE.search(a["href"])
        if not m:
            continue
        text = " ".join(a.get_text(" ", strip=True).split())
        events[m.group(1)] = {
            "text": text,
            "full": "FULL" in text.upper(),
            "url": "https://book.volleyballfriends.de" + m.group(0),
        }
    return events


def notify(title, message, click_url, tags="volleyball"):
    if not NTFY_TOPIC:
        print("NTFY_TOPIC fehlt, Nachricht wäre:", title, message)
        return
    requests.post(
        f"https://ntfy.sh/{NTFY_TOPIC}",
        data=message.encode("utf-8"),
        headers={
            "Title": title.encode("utf-8"),
            "Click": click_url,
            "Tags": tags,
            "Priority": "high",
        },
        timeout=30,
    ).raise_for_status()


def main():
    events = fetch_events()
    if not events:
        # Seite evtl. kaputt oder umgebaut: nichts überschreiben, Fehler melden
        print("Keine Events gefunden, breche ab.", file=sys.stderr)
        sys.exit(1)

    first_run = not STATE_FILE.exists()
    old = {} if first_run else json.loads(STATE_FILE.read_text())

    if first_run:
        notify(
            "Volleyball-Watcher aktiv",
            f"{len(events)} Events aktuell bekannt. Ab jetzt gibt's Push bei neuen.",
            URL,
        )
    else:
        for eid, ev in events.items():
            if eid not in old:
                notify("Neues Volleyball-Event", ev["text"], ev["url"])
            elif NOTIFY_FREED_SPOTS and old[eid].get("full") and not ev["full"]:
                notify("Platz frei geworden", ev["text"], ev["url"], tags="tada")

    # Zustand nur schreiben, wenn sich etwas geändert hat (vermeidet unnötige Commits)
    new_state = {eid: {"full": ev["full"]} for eid, ev in events.items()}
    if new_state != old:
        STATE_FILE.write_text(json.dumps(new_state, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
