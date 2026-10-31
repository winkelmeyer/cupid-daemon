import sys
import uiautomator2 as u2
from PIL import Image
d = u2.connect()
for cmd in sys.argv[1:]:
    kind, _, arg = cmd.partition(":")
    if kind == "text":
        d(text=arg).click()
    elif kind == "type":
        d.send_keys(arg, clear=True)
    elif kind == "tap":
        x, y = arg.split(",")
        d.click(int(x), int(y))
    elif kind == "wait":
        d.sleep(float(arg))
d.sleep(1.5)
img = d.screenshot()
img.resize((540, 1200)).save("screen.png")
print(d.app_current()["package"])
import xml.etree.ElementTree as ET
for n in ET.fromstring(d.dump_hierarchy()).iter("node"):
    t = n.get("text") or n.get("content-desc")
    if t and len(t) > 2 and not t.endswith("notification: ") and "emoji" not in t:
        print(repr(t), n.get("bounds"), n.get("class").split(".")[-1])
