venv/bin/python next_match.py 2>&1 | grep -vE "^(Start sending|They help|Add date ideas|Try it|Choose a time|Let’s get|Keep going|We're learning|Signals|Learning your type|One like goes|Add your own|[0-9]:[0-9]{2}$|[0-9]+\.[0-9]+$)"
venv/bin/python -c "
import uiautomator2 as u2, xml.etree.ElementTree as ET; d=u2.connect()
seen=[]
for _ in range(8):
  for n in ET.fromstring(d.dump_hierarchy()).iter('node'):
    t=n.get('content-desc') or ''
    if t.startswith(('Prompt','Poll')) and t not in seen: seen.append(t)
  d.shell('input swipe 540 1800 540 900 300'); d.sleep(1)
print('\n'.join(seen))
for _ in range(4): d.shell('input swipe 540 600 540 2000 100')"
