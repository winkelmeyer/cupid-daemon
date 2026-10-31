import xml.etree.ElementTree as ET
import uiautomator2 as u2

d = u2.connect()
seen = []
for _ in range(6):
    for n in ET.fromstring(d.dump_hierarchy()).iter("node"):
        t = n.get("text") or ""
        if len(t) > 1 and t not in seen and not t.startswith(("Tello", "Battery")) and ":" not in t[:3]:
            seen.append(t)
    d.shell("input swipe 540 1800 540 900 300")
    d.sleep(1)
print("\n".join(seen))
d.shell("input swipe 540 600 540 2000 100"); d.shell("input swipe 540 600 540 2000 100"); d.shell("input swipe 540 600 540 2000 100")
