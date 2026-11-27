# Auto Scheduler - cloud watcher v2 (runs on GitHub Actions)
# Reads every ACTIVE watch from Firebase, checks its booking page,
# sends an urgent ntfy alert to that watch's topic when booking opens (once),
# and updates "lastChecked" so the app shows "Last checked X min ago".
import json, os, time, re, urllib.request
import firebase_admin
from firebase_admin import credentials, firestore

SITE_URL = os.environ.get("SITE_URL", "").rstrip("/")
key = json.loads(os.environ["FIREBASE_KEY"])
firebase_admin.initialize_app(credentials.Certificate(key))
db = firestore.client()

OPEN_WORDS = re.compile(r"bookings? (are )?open|book now|booking started", re.I)

def fetch(url):
    sep = "&" if "?" in url else "?"
    req = urllib.request.Request(f"{url}{sep}t={int(time.time())}", headers={"User-Agent": "AutoScheduler-test/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", "ignore")

def is_open(link):
    """True/False, or None if the page could not be checked."""
    base = link.rstrip("/")
    # Our ShowTix test site: read status.json (fast: local repo copy if it is this site)
    if SITE_URL and base.startswith(SITE_URL) and os.path.exists("status.json"):
        return bool(json.load(open("status.json")).get("open"))
    try:
        return bool(json.loads(fetch(base + "/status.json")).get("open"))
    except Exception:
        pass
    try:
        return bool(OPEN_WORDS.search(fetch(link)))
    except Exception as e:
        print("  could not check:", e)
        return None

def push(topic, title, msg, link):
    req = urllib.request.Request(f"https://ntfy.sh/{topic}", data=msg.encode("utf-8"),
        headers={"Title": title, "Priority": "urgent", "Tags": "rotating_light", "Click": link or ""})
    urllib.request.urlopen(req, timeout=20)

watches = list(db.collection("watches").where("active", "==", True).stream())
print(f"Active watches: {len(watches)}")

for doc in watches:
    w = doc.to_dict()
    name, link, topic = w.get("name", "?"), w.get("link", ""), w.get("topic", "")
    print(f"- {name} | {link}")
    if not link or not topic:
        print("  skipped (no link or no ntfy topic)")
        continue
    state = is_open(link)
    update = {"lastChecked": firestore.SERVER_TIMESTAMP}
    if state is True and not w.get("alerted"):
        extra = f" · {w.get('count')} tickets" if w.get("count") else ""
        pref = f" · prefers {w['pref']}" if w.get("pref") else ""
        msg = f"{name} at {w.get('place','')} is OPEN{extra}{pref}. Tap to book now!"
        push(topic, "Auto Scheduler: Booking OPEN", msg, link)
        update.update({"alerted": True, "openedAt": firestore.SERVER_TIMESTAMP})
        print("  OPEN -> alert sent")
    elif state is False and w.get("alerted"):
        update["alerted"] = False
        print("  closed again -> reset")
    else:
        print("  open (already alerted)" if state else "  not open yet" if state is False else "  check failed")
    doc.reference.update(update)
print("Done")
