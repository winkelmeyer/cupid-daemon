import random
import time
from swipe import log, read_profile, rule_verdict
import uiautomator2 as u2

d = u2.connect()
for _ in range(8):
    button = d(descriptionStartsWith="Skip ")
    name = button.info["contentDescription"].removeprefix("Skip ")
    lines = read_profile(d)
    reason = rule_verdict(lines)
    if not reason:
        print(f"PASSES RULES: {name}")
        print("\n".join(lines))
        d.screenshot("current.png")
        break
    button.click()
    log(f"hinge {name} skip (rule: {reason})")
    time.sleep(random.uniform(4, 10))
