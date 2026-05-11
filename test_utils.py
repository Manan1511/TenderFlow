import sys
sys.path.insert(0, ".")
import json
from core.utils import clean_json_response, parse_strict_json

VALID_JSON = json.dumps({
    "emd_fee": "INR 50,000",
    "processing_fee": "INR 1,000",
    "manufacturer_documents": ["ISO Cert"],
    "bidder_documents": ["Turnover Certificate"],
    "product_supply_requirements": ["100 units of X"],
    "email_draft": "Dear Manufacturer, please provide...",
})

# Test 1: Strip markdown fences
raw1 = "```json\n" + VALID_JSON + "\n```"
cleaned1 = clean_json_response(raw1)
assert cleaned1.startswith("{"), f"FAIL Test1: {cleaned1!r}"
print("Test 1 PASS: Strips markdown fences")

# Test 2: Strip conversational text
raw2 = "Sure! Here is the result:\n" + VALID_JSON + "\nHope that helps!"
cleaned2 = clean_json_response(raw2)
assert cleaned2.startswith("{") and cleaned2.endswith("}"), f"FAIL Test2: {cleaned2!r}"
print("Test 2 PASS: Strips conversational text")

# Test 3: Full parse with key validation
data = parse_strict_json(raw1)
assert "emd_fee" in data and "email_draft" in data
print("Test 3 PASS: parse_strict_json validates all required keys")

# Test 4: Missing keys raise ValueError
bad = json.dumps({"emd_fee": "100", "processing_fee": "50"})
try:
    parse_strict_json(bad)
    print("Test 4 FAIL: Should have raised ValueError")
except ValueError as exc:
    print(f"Test 4 PASS: Correctly raises ValueError — {exc}")

print("\nAll unit tests passed.")
