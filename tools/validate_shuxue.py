# -*- coding: utf-8 -*-
"""Validate shuxue bank: structure + independent recompute of pure-expression questions."""
import json, re, sys, glob, os
from fractions import Fraction as F

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bank", "shuxue")
num_re = re.compile(r"\d+/\d+|\d+\.\d+|\d+")

def to_expr(s):
    s = s.replace("×", "*").replace("÷", "/").replace("[", "(").replace("]", ")")
    s = re.sub(r"(\d+)/(\d+)", r"F(\1,\2)", s)
    s = re.sub(r"(\d+\.\d+)", r"F('\1')", s)
    s = re.sub(r"(?<![\w'(,])(\d+)(?![\d,'.)]*\))", r"F(\1)", s) if False else s
    return s

def val(ans):
    ans = ans.strip()
    if ans.endswith("%"): return F(ans[:-1]) / 100
    if re.fullmatch(r"-?\d+/\d+", ans): a, b = ans.split("/"); return F(int(a), int(b))
    return F(ans)

def check_expr(q, answers):
    m = re.fullmatch(r"(?:简便计算：)?([\d\.\s/+\-×÷()\[\]]+)= ？(?:（[^）]*）)?", q)
    if not m: return None
    expr = m.group(1).strip()
    py = expr.replace("×", "*").replace("÷", "/").replace("[", "(").replace("]", ")")
    py = re.sub(r"(\d+/\d+|\d+\.\d+|\d+)", lambda m: "(F(" + ",".join(repr(x) for x in m.group(1).split("/")) + "))" if "/" in m.group(1) else "F(" + repr(m.group(1)) + ")", py)
    py = re.sub(r"F\('(\d+)'\)", r"F(\1)", py).replace("(F('", "(F(").replace("','", ",").replace("'))", "))")
    true = eval(py, {"F": F})
    return all(val(a) == true for a in answers if re.fullmatch(r"-?[\d./]+%?", a))

def main():
    ok_all = True; report = []
    for p in sorted(glob.glob(os.path.join(D, "g*.json"))):
        name = os.path.basename(p)
        data = json.load(open(p, encoding="utf-8"))
        errs = []; checked = 0
        qs = [d["q"] for d in data]
        if len(set(qs)) != len(qs): errs.append("duplicate q")
        if len(data) < 30: errs.append(f"only {len(data)} items")
        for d in data:
            for k in ("type", "subject", "topic", "unit", "q"):
                if not d.get(k): errs.append(f"missing {k}: {d}")
            if d["subject"] != "数学" or d["topic"] != "综合": errs.append("bad subject/topic")
            if d["type"] == "choice":
                o = d.get("options", [])
                if len(o) != 4 or len(set(o)) != 4: errs.append(f"options: {d['q']} {o}")
                ans = [o[0]] if o else []
            elif d["type"] == "fill":
                ans = d.get("answers", [])
                if not ans or any(not str(a).strip() for a in ans): errs.append(f"answers: {d['q']}")
            else:
                errs.append("bad type"); ans = []
            try:
                r = check_expr(d["q"], ans)
            except Exception as e:
                r = None
            if r is not None:
                checked += 1
                if not r: errs.append(f"WRONG: {d['q']} -> {ans}")
        units = sorted(set(d["unit"] for d in data))
        report.append(f"{name}: {len(data)} items, {checked} expr re-checked, {len(units)} units, errors={len(errs)}")
        for e in errs[:10]: report.append("   " + e)
        ok_all &= not errs
    print("\n".join(report)); print("ALL OK" if ok_all else "ERRORS")
    return ok_all

if __name__ == "__main__":
    sys.exit(0 if main() else 1)
