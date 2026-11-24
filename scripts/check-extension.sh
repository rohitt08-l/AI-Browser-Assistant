#!/usr/bin/env bash
# Static checks for the extension: manifest validity, referenced files exist, JS parses.
set -euo pipefail
cd "$(dirname "$0")/../extension"

python3 - <<'PY'
import json, os, re, sys
m = json.load(open("manifest.json"))
errors = []
assert m["manifest_version"] == 3, "manifest_version must be 3"
if not re.fullmatch(r"\d+(\.\d+){0,3}", m["version"]):
    errors.append(f"invalid version {m['version']!r}")
refs = [m["background"]["service_worker"], m["side_panel"]["default_path"]]
for html in [p for p in refs if p.endswith(".html")]:
    refs += re.findall(r'(?:src|href)="([^":]+)"', open(html).read())
for ref in refs:
    if not os.path.isfile(ref):
        errors.append(f"missing file referenced: {ref}")
if errors:
    sys.exit("\n".join(errors))
print(f"manifest OK (v{m['version']}), {len(refs)} referenced files present")
PY

for f in *.js; do node --check "$f"; done
echo "JS syntax OK"
