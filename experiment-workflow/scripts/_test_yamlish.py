"""_yamlish 往返测试：解析→序列化→再解析必须完全一致。"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
from _yamlish import loads, dumps, YamlError

CASES = [
    {},
    {"a": 1, "b": 2.5, "c": True, "d": None, "e": "文本"},
    {"list": [1, 2, 3], "empty": [], "nested": {"x": {"y": "z"}}},
    {"items": [{"id": "20261031-A", "q": 12.5, "unit": "mL"},
               {"id": "20261031-A-1", "q": 0.5, "unit": "mL"}]},
    {"str": "含: 冒号", "str2": "#井号", "str3": "-破折号", "str4": "true", "str5": "123", "str6": ""},
    {"multi": "第一行\n第二行"},
    {"deep": [{"a": [{"b": 1}, {"b": 2}]}]},
    {"units": {"convert": [["mg", "g"], ["uL", "mL"]]}},
]

SRC = """\
# 注释应被忽略
id: 20261031-A
kind: base
status: in_stock
location: 4℃冰箱 A2
quantity: 12.5
unit: mL
concentrations:
  - value: 10
    unit: mM
    analyte: 葡萄糖
    origin: measured
  - value: 0.5
    unit: "%"
    analyte: 血清
    origin: calculated
    basis: 由母液稀释
treatment: 药物X 10 µM, 24 h
formed_on: "2026-10-31"
parent: null
sources: []
experiments: [20261031-143012]
history:
  - at: 2026-10-31T15:30:00+08:00
    type: create
    delta: 12.5
    key: abc
    note: 初始入库
  - at: 2026-10-31T16:00:00+08:00
    type: consume
    delta: -2
    key: def
    note: ""
"""

failures = 0


def check(name, cond, detail=""):
    global failures
    if not cond:
        failures += 1
        print(f"FAIL {name} {detail}")
    else:
        print(f"ok   {name}")


for idx, case in enumerate(CASES):
    text = dumps(case)
    back = loads(text)
    check(f"roundtrip-{idx}", back == case, f"\n--- src ---\n{text}--- got ---\n{back!r}")

parsed = loads(SRC)
check("src.id", parsed["id"] == "20261031-A")
check("src.qty", parsed["quantity"] == 12.5)
check("src.conc[0].analyte", parsed["concentrations"][0]["analyte"] == "葡萄糖")
check("src.conc[1].unit", parsed["concentrations"][1]["unit"] == "%")
check("src.parent", parsed["parent"] is None)
check("src.sources", parsed["sources"] == [])
check("src.experiments", parsed["experiments"] == ["20261031-143012"], f"got {parsed['experiments']!r}")
check("src.history[1].note", parsed["history"][1]["note"] == "")
check("src.history[0].at", parsed["history"][0]["at"] == "2026-10-31T15:30:00+08:00")

again = loads(dumps(parsed))
check("src-roundtrip", again == parsed)

check("empty", loads("") is None)
check("comment-only", loads("# nothing\n") is None)

for bad, label in [("a:\n\tb: 1", "tab-indent"), ("a: [1, 2", "unclosed-flow"), ('a: "x', "unclosed-quote")]:
    try:
        loads(bad)
        check(f"reject-{label}", False, "应当报错但没有")
    except YamlError:
        check(f"reject-{label}", True)

block = loads("note: |\n  line1\n  line2\n")
check("block-scalar", block["note"] == "line1\nline2", repr(block))

print("\n%d failures" % failures)
sys.exit(1 if failures else 0)
