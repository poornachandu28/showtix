# Auto Scheduler - cloud watcher (runs on GitHub Actions)
# Checks the ShowTix status file. When bookings open, it sends a push
# notification (ntfy) and rings your phone (Twilio) - only once per opening.
import json, os, base64, urllib.request, urllib.parse, time

SITE_URL   = os.environ["SITE_URL"].rstrip("/")      # e.g. https://you.github.io/showtix
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")
TW_SID     = os.environ.get("TWILIO_SID", "")
TW_TOKEN   = os.environ.get("TWILIO_TOKEN", "")
TW_FROM    = os.environ.get("TWILIO_FROM", "")
MY_PHONE   = os.environ.get("MY_PHONE", "")
STATE_FILE = "alerted.txt"   # remembers we already alerted, so it rings only once

def get_status():
    url = f"{SITE_URL}/status.json?t={int(time.time())}"
    with urllib.request.urlopen(url, timeout=20) as r:
        return json.loads(r.read())

def push(title, msg):
    if not NTFY_TOPIC: return
    req = urllib.request.Request(f"https://ntfy.sh/{NTFY_TOPIC}", data=msg.encode(),
        headers={"Title": title, "Priority": "urgent", "Tags": "rotating_light",
                 "Click": SITE_URL + "/"})
    urllib.request.urlopen(req, timeout=20); print("Push sent")

def call(text):
    if not (TW_SID and TW_TOKEN and TW_FROM and MY_PHONE): return
    twiml = f'<Response><Say voice="alice">{text}</Say><Pause length="1"/><Say voice="alice">{text}</Say></Response>'
    data = urllib.parse.urlencode({"To": MY_PHONE, "From": TW_FROM, "Twiml": twiml}).encode()
    auth = base64.b64encode(f"{TW_SID}:{TW_TOKEN}".encode()).decode()
    req = urllib.request.Request(f"https://api.twilio.com/2010-04-01/Accounts/{TW_SID}/Calls.json",
        data=data, headers={"Authorization": "Basic " + auth})
    urllib.request.urlopen(req, timeout=20); print("Call placed")

s = get_status()
already = os.path.exists(STATE_FILE)
print("Status:", s, "| already alerted:", already)

if s.get("open") and not already:
    msg = f'{s["movie"]} bookings are OPEN at {s["theatre"]}, {s["show"]}. Book now!'
    push("Auto Scheduler: Bookings OPEN", msg)
    call(f'Auto Scheduler alert. {s["movie"]} bookings are now open at {s["theatre"]}. Open the app to book.')
    open(STATE_FILE, "w").write(time.strftime("%Y-%m-%d %H:%M UTC"))
elif not s.get("open") and already:
    os.remove(STATE_FILE); print("Bookings closed again - reset, ready for next opening")
else:
    print("Nothing to do")
