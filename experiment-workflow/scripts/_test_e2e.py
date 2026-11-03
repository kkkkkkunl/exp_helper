"""端到端测试：在临时目录建一个项目，跑完整流程并断言结果。

覆盖：配置定位、编号分配（含并发重号）、库存两段式与幂等、
单位换算与跨维度拒绝、归档去重、结果版本与标记、跨项目筛选。
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = sys.executable
FAILS = []
COUNTER = [0]

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


def run(script, *args, cwd=None, expect_fail=False):
    args = list(args)
    if script == "inventory.py" and args[0] == "plan":
        path = Path(args[args.index("--items")+1])
        rows = json.loads(path.read_text(encoding="utf-8"))
        for index, row in enumerate(rows):
            row.setdefault("event_id", path.stem + "-" + str(index))
        path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    if script == "inventory.py" and args[0] == "commit":
        import _common as C
        root = Path(args[args.index("--project")+1])
        eid = args[args.index("--experiment")+1]
        plan = C._yamlish.loads((root / "实验" / eid / ".experiment-workflow-plan.yaml").read_text(encoding="utf-8"))
        args += ["--plan-hash", plan["hash"], "--confirmed-by", "synthetic-test"]
    # 沙箱禁止管道 stdio，改用文件重定向
    COUNTER[0] += 1
    tmp = HERE.parent.parent / "_e2e_run" / f"io-{os.getpid()}-{COUNTER[0]}"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    out_path, err_path = tmp.with_suffix(".out"), tmp.with_suffix(".err")
    with open(out_path, "w", encoding="utf-8") as fout, open(err_path, "w", encoding="utf-8") as ferr:
        proc = subprocess.run(
            [PY, str(HERE / script), *map(str, args)],
            stdout=fout, stderr=ferr, cwd=cwd,
        )
    stdout = out_path.read_text(encoding="utf-8")
    stderr = err_path.read_text(encoding="utf-8")
    try:
        payload = json.loads(stdout) if stdout.strip() else {}
    except json.JSONDecodeError:
        payload = {"_raw": stdout, "_err": stderr}
    if expect_fail:
        if proc.returncode == 0:
            FAILS.append(f"{script} {' '.join(args)} 期望失败但成功了")
    elif proc.returncode != 0:
        FAILS.append(f"{script} {' '.join(args)} 失败: {stdout} {stderr}")
    return payload


def check(name, cond, detail=""):
    if not cond:
        FAILS.append(f"{name} {detail}")
        print(f"FAIL {name} {detail}")
    else:
        print(f"ok   {name}")


def main():
    # 注意：不能用 tempfile.mkdtemp —— 它以 0700 建目录，沙箱 token 之后
    # 无法在其下创建子目录。用普通 mkdir 建测试目录。
    base = Path(__file__).resolve().parents[2] / "_e2e_run"
    base.mkdir(parents=True, exist_ok=True)
    root = base / f"run-{os.getpid()}"
    if root.exists():
        shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)
    try:
        kb = root / "kb"
        (kb / "samples").mkdir(parents=True)
        proj = root / "demo"
        (proj / "templates").mkdir(parents=True)
        (proj / "templates" / "cell-culture.md").write_text("# 细胞培养\n1. 接种\n", encoding="utf-8")
        (proj / "experiment-project.yaml").write_text(
            """\
version: 1
project: 演示课题
knowledge_base: ../kb
sample_library: samples
method_templates:
  - name: 细胞培养
    path: templates/cell-culture.md
    version: "2026-10-01"
    default: true
analysis_skills:
  flow-analysis: templates/cell-culture.md
analysis_map:
  - match:
      experiment_type: 流式
    skill: flow-analysis
units:
  convert:
    - [uL, mL]
    - [mg, g]
""",
            encoding="utf-8",
        )

        # 1 配置
        found = run("project.py", "find", "--path", str(proj))
        check("find", found.get("root") == str(proj), found)
        shown = run("project.py", "show", "--project", str(proj))
        check("show.kb", shown.get("knowledge_base") == str(kb), shown.get("knowledge_base"))
        check("show.default", shown.get("default_template") == "细胞培养")
        valid = run("project.py", "validate", "--project", str(proj))
        check("validate", valid.get("ok_to_run") is True, valid.get("problems"))
        disp = run("project.py", "dispatch", "--project", str(proj), "--experiment-type", "流式")
        check("dispatch.hit", disp.get("skill") == "flow-analysis", disp)
        disp2 = run("project.py", "dispatch", "--project", str(proj), "--experiment-type", "未知")
        check("dispatch.miss", disp2.get("skill") is None and "message" in disp2, disp2)

        # 2 实验编号
        exp = run("allocate_id.py", "experiment", "--project", str(proj))
        exp_id = exp.get("id", "")
        check("exp.id-format", len(exp_id) == 15 and exp_id[8] == "-", exp_id)
        check("exp.dir", (proj / "实验" / exp_id / "原始附件").is_dir())

        # 3 样本编号：同一天连续分配应得 A、B
        s1 = run("allocate_id.py", "sample", "--project", str(proj), "--date", "20261031").get("id")
        s2 = run("allocate_id.py", "sample", "--project", str(proj), "--date", "20261031").get("id")
        s3 = run("allocate_id.py", "sample", "--project", str(proj), "--date", "20261101").get("id")
        check("sample.A", s1 == "20261031-A", s1)
        check("sample.B", s2 == "20261031-B", s2)
        check("sample.other-day-resets", s3 == "20261101-A", s3)

        # 4 分装编号
        ali = run("allocate_id.py", "aliquot", "--project", str(proj), "--parent", "20261031-A", "--count", 2)
        check("aliquot", ali.get("children") == ["20261031-A-1", "20261031-A-2"], ali)
        ali2 = run("allocate_id.py", "aliquot", "--project", str(proj), "--parent", "20261031-A", "--count", 1)
        check("aliquot.no-reuse", ali2.get("children") == ["20261031-A-3"], ali2)

        # 5 库存：起始量未知时拒绝扣减
        items_bad = root / "bad.json"
        items_bad.write_text(json.dumps([{"sample": "20261031-A", "type": "consume", "delta": -1}]), encoding="utf-8")
        bad = run("inventory.py", "plan", "--project", str(proj), "--experiment", exp_id,
                  "--items", str(items_bad), expect_fail=True)
        check("no-backfill", "起始量未知" in json.dumps(bad, ensure_ascii=False), bad)

        # 6 正常入库 + 取用 + 单位换算
        items_ok = root / "ok.json"
        items_ok.write_text(json.dumps([
            {"sample": "20261031-A", "type": "create", "delta": 10, "unit": "mL",
             "location": "4℃冰箱A2", "note": "初始入库"},
            {"sample": "20261031-A", "type": "consume", "delta": -2000, "unit": "uL",
             "note": "取用 2 mL，按 uL 记录"},
        ], ensure_ascii=False), encoding="utf-8")
        plan = run("inventory.py", "plan", "--project", str(proj), "--experiment", exp_id,
                   "--items", str(items_ok))
        check("plan.items", plan.get("items") == 2, plan)
        checklist = Path(plan.get("checklist", ""))
        check("plan.checklist", checklist.is_file() and "待用户确认" in checklist.read_text(encoding="utf-8"))

        # 提交前台账未变
        pre = run("inventory.py", "history", "--project", str(proj), "--sample", "20261031-A")
        check("commit.not-yet", pre.get("quantity") is None, pre)

        committed = run("inventory.py", "commit", "--project", str(proj), "--experiment", exp_id)
        check("commit.count", len(committed.get("committed", [])) == 2, committed)
        post = run("inventory.py", "history", "--project", str(proj), "--sample", "20261031-A")
        check("commit.quantity", post.get("quantity") == 8, post.get("quantity"))
        check("commit.unit", post.get("unit") == "mL", post.get("unit"))

        # 7 幂等：同一份清单再提交不应重复扣减
        again = run("inventory.py", "commit", "--project", str(proj), "--experiment", exp_id,
                    expect_fail=False)
        after = run("inventory.py", "history", "--project", str(proj), "--sample", "20261031-A")
        check("idempotent", after.get("quantity") == 8, after.get("quantity"))
        check("idempotent-receipt-retained", again.get("ok") is True and again.get("noop") is True, again)

        # 8 库存不足
        items_over = root / "over.json"
        items_over.write_text(json.dumps([{"sample": "20261031-A", "type": "consume", "delta": -99}]), encoding="utf-8")
        over = run("inventory.py", "plan", "--project", str(proj), "--experiment", exp_id,
                   "--items", str(items_over), expect_fail=True)
        check("insufficient", "库存不足" in json.dumps(over, ensure_ascii=False), over)

        # 9 跨维度换算拒绝（mL 与 g 不同维度）
        items_dim = root / "dim.json"
        items_dim.write_text(json.dumps([
            {"sample": "20261031-A", "type": "create", "delta": 5, "unit": "mL"},
        ]), encoding="utf-8")
        run("inventory.py", "plan", "--project", str(proj), "--experiment", exp_id,
            "--items", str(items_dim), expect_fail=True)  # 已有起始量，create 应被拒
        items_dim2 = root / "dim2.json"
        items_dim2.write_text(json.dumps([
            {"sample": "20261031-B", "type": "create", "delta": 5, "unit": "mL"},
            {"sample": "20261031-B", "type": "consume", "delta": -1, "unit": "g"},
        ]), encoding="utf-8")
        dim = run("inventory.py", "plan", "--project", str(proj), "--experiment", exp_id,
                  "--items", str(items_dim2), expect_fail=True)
        check("no-cross-dimension", "不得换算" in json.dumps(dim, ensure_ascii=False), dim)

        # 10 归档
        src1 = root / "raw.csv"
        src1.write_text("a,b\n1,2\n", encoding="utf-8")
        src2 = root / "notes.txt"
        src2.write_text("hello\n", encoding="utf-8")
        arch = run("archive.py", "move", "--project", str(proj), "--experiment", exp_id,
                   "--files", str(src1), str(src2))
        check("archive.count", len(arch.get("archived", [])) == 2, arch)
        check("archive.source-removed", not src1.exists() and not src2.exists())
        first = arch["archived"][0]
        check("archive.link", bool(first.get("link")) and
              (first["link"].startswith("[[") or first.get("outside_vault") is True), first)

        # 同名冲突：再放一个同名不同内容
        src3 = root / "raw.csv"
        src3.write_text("different\n", encoding="utf-8")
        arch2 = run("archive.py", "move", "--project", str(proj), "--experiment", exp_id,
                    "--files", str(src3))
        check("archive.conflict", len(arch2.get("blocked", [])) == 1, arch2)
        check("archive.conflict-keeps-source", src3.exists())

        # 11 结果项与版本
        img = root / "curve.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\nfake")
        tbl = root / "table.csv"
        tbl.write_text("group,mean\n", encoding="utf-8")
        res = run("results.py", "new", "--project", str(proj), "--experiment", exp_id, "--title", "增殖曲线")
        rid = res.get("id", "")
        check("result.id", rid == f"R-{exp_id}-01", rid)

        v1 = run("results.py", "add-version", "--project", str(proj), "--id", rid,
                 "--files", str(img), str(tbl), "--params", "t 检验, α=0.05")
        check("result.v1", v1.get("version") == 1, v1)
        check("result.unmarked", v1.get("marked") is False)

        noop = run("results.py", "add-version", "--project", str(proj), "--id", rid,
                   "--files", str(img), str(tbl), "--params", "t 检验, α=0.05")
        check("result.noop", noop.get("noop") is True, noop)

        v2 = run("results.py", "add-version", "--project", str(proj), "--id", rid,
                 "--files", str(img), "--params", "t 检验, α=0.01")
        check("result.v2", v2.get("version") == 2, v2)

        run("results.py", "mark", "--project", str(proj), "--id", rid, "--version", 1)
        marked = run("results.py", "list", "--project", str(proj), "--marked")
        check("result.marked-v1", marked.get("count") == 1 and marked["results"][0]["version"] == 1, marked)

        v3 = run("results.py", "add-version", "--project", str(proj), "--id", rid,
                 "--files", str(tbl), "--params", "t 检验, α=0.01, 去异常值")
        check("result.v3", v3.get("version") == 3, v3)
        still = run("results.py", "list", "--project", str(proj), "--marked")
        check("result.old-mark-kept", still.get("count") == 1 and still["results"][0]["version"] == 1, still)

        cross = run("results.py", "filter", "--kb", str(kb), "--marked")
        check("filter.cross-project", cross.get("count") == 1, cross)

        # 12 在库列表
        stock = run("inventory.py", "list", "--project", str(proj))
        ids = [row["id"] for row in stock.get("samples", [])]
        check("stock.has-A", "20261031-A" in ids, ids)

        print()
        if FAILS:
            print(f"{len(FAILS)} 项失败：")
            for f in FAILS:
                print(" -", f)
            return 1
        print("全部通过")
        return 0
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
