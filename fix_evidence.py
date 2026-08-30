with open("backend/app/routers/evidence.py", "r") as f:
    content = f.read()

import re
endpoints_to_fix = [
    "create_transfer",
    "seal_evidence",
    "start_analysis",
    "complete_analysis",
    "submit_evidence",
]

for ep in endpoints_to_fix:
    pattern = r'(def ' + ep + r'\(.*?evidence = get_evidence\(db, evidence_id\)\n\s+get_case_for_user\(db, user, evidence\.case_id)'
    content = re.sub(pattern, r'\1, require_write=True)', content, flags=re.DOTALL)

with open("backend/app/routers/evidence.py", "w") as f:
    f.write(content)
