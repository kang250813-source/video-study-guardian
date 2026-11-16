# -*- coding: utf-8 -*-
"""数学题库生成器 — 人教版(2024新版)小学数学 1上~6下.
All answers are computed by code. Seeded => reproducible.
Usage: python3 gen_shuxue.py [vol ...]   (default: g6a g1a g2a g3a g4a g5a g1b g2b g3b g4b g5b g6b)
Output: bank/shuxue/<vol>.json
"""
import json, random, sys, os
from fractions import Fraction as F
from math import gcd

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bank", "shuxue")
PI = F(314, 100)

# ---------------- formatting helpers ----------------
def is_term(x):
    x = F(x); d = x.denominator
    for p in (2, 5):
        while d % p == 0: d //= p
    return d == 1

def dec(x):
    """exact decimal string for a terminating Fraction/int"""
    x = F(x)
    if x.denominator == 1: return str(x.numerator)
    assert is_term(x)
    neg = x < 0; x = abs(x); k = 0
    while (x * 10**k).denominator != 1: k += 1
    n = (x * 10**k).numerator
    s = str(n).rjust(k + 1, "0")
    s = s[:-k] + "." + s[-k:]
    return ("-" if neg else "") + s

def fs(x):
    x = F(x)
    return str(x.numerator) if x.denominator == 1 else f"{x.numerator}/{x.denominator}"

def fans(x):
    """accepted answers for a fraction value"""
    x = F(x); a = [fs(x)]
    if x.denominator != 1 and is_term(x): a.append(dec(x))
    return a

def num(x):
    x = F(x)
    return dec(x) if is_term(x) else fs(x)

def numopts(correct, cands, allow_neg=False, step=None):
    c = num(correct); out = [c]
    for w in cands:
        try:
            if not allow_neg and F(w) < 0: continue
            s = num(w) if is_term(w) else f"{float(F(w)):.2f}"
        except Exception:
            s = str(w)
        if s not in out: out.append(s)
        if len(out) == 4: return out
    st = F(step) if step else (F(1) if F(correct).denominator == 1 else F(1, F(correct).denominator))
    k = 1
    while len(out) < 4:
        for v in (F(correct) + st * k, F(correct) - st * k):
            if (allow_neg or v >= 0):
                s = num(v)
                if s not in out and len(out) < 4: out.append(s)
        k += 1
    return out

CN = "零一二三四五六七八九十"
NAMES = ["小明", "小红", "小华", "小丽", "小刚", "小芳", "乐乐", "笑笑", "淘气", "丁丁", "冬冬", "明明"]

# ---------------- bank ----------------
class Bank:
    def __init__(self, vol, seed):
        self.vol = vol; self.r = random.Random(seed); self.items = []; self.qs = set()

    def add(self, unit, spec):
        if spec is None: return False
        kind, q = spec[0], spec[1]
        if q in self.qs: return False
        if kind == "c":
            opts = []
            for o in spec[2]:
                o = str(o)
                if o not in opts: opts.append(o)
            if len(opts) < 4: return False
            it = {"type": "choice", "subject": "数学", "topic": "综合", "unit": unit, "q": q, "options": opts[:4]}
        else:
            ans = []
            for a in spec[2]:
                a = str(a)
                if a not in ans: ans.append(a)
            it = {"type": "fill", "subject": "数学", "topic": "综合", "unit": unit, "q": q, "answers": ans}
        self.qs.add(q); self.items.append(it); return True

    def run(self, units, total=84):
        per = max(6, total // len(units))
        for unit, gens in units:
            got, tries = 0, 0
            while got < per and tries < per * 40:
                tries += 1
                g = gens[tries % len(gens)]
                if self.add(unit, g(self.r)): got += 1
        return self.items

def C(q, opts): return ("c", q, opts)
def Fi(q, ans): return ("f", q, ans if isinstance(ans, list) else [ans])

def fact(bank):
    """generator from a fixed list of (q, [correct, w1, w2, w3]) or (q, answer-str)"""
    def g(r):
        q, a = r.choice(bank)
        return C(q, a) if isinstance(a, list) else Fi(q, a)
    return g

# ---------------- generic arithmetic generators ----------------
def g_add(lo, hi, maxsum, carry=None, fillp=0.6):
    def g(r):
        a, b = r.randint(lo, hi), r.randint(lo, hi)
        if a + b > maxsum: return None
        if carry is True and (a % 10 + b % 10) < 10: return None
        if carry is False and (a % 10 + b % 10) >= 10: return None
        s = a + b; q = f"{a} + {b} = ？"
        if r.random() < fillp: return Fi(q, str(s))
        return C(q, numopts(s, [s - 10, s + 10, s - 1, s + 1, abs(a - b)]))
    return g

def g_sub(lo, hi, borrow=None, fillp=0.6, minb=1):
    def g(r):
        a = r.randint(lo, hi); b = r.randint(minb, a)
        if borrow is True and a % 10 >= b % 10: return None
        if borrow is False and a % 10 < b % 10: return None
        d = a - b; q = f"{a} - {b} = ？"
        if r.random() < fillp: return Fi(q, str(d))
        # common mistake: subtract smaller digit from larger
        wrong = abs(a % 10 - b % 10) + (a // 10 - b // 10) * 10
        return C(q, numopts(d, [wrong, d + 10, d - 1, d + 1, a + b]))
    return g

def g_mul(alo, ahi, blo, bhi, fillp=0.6):
    def g(r):
        a, b = r.randint(alo, ahi), r.randint(blo, bhi)
        p = a * b; q = f"{a} × {b} = ？"
        if r.random() < fillp: return Fi(q, str(p))
        return C(q, numopts(p, [p + a, p - a, p + b, a + b, p + 10]))
    return g

def g_div(dlo, dhi, qlo, qhi, fillp=0.6):
    def g(r):
        d, qt = r.randint(dlo, dhi), r.randint(qlo, qhi)
        n = d * qt; q = f"{n} ÷ {d} = ？"
        if r.random() < fillp: return Fi(q, str(qt))
        return C(q, numopts(qt, [qt + 1, qt - 1, n - d, qt * 10, d]))
    return g

def g_mixed_review(gens):
    def g(r): return r.choice(gens)(r)
    return g

# =====================================================================
# 1上
# =====================================================================
def u1a_1():
    def fen(r):
        n = r.randint(2, 5); a = r.randint(1, n - 1)
        return Fi(f"{n}可以分成{a}和（　）。", str(n - a))
    def cmp(r):
        a, b = r.randint(0, 5), r.randint(0, 5)
        s = ">" if a > b else "<" if a < b else "="
        return Fi(f"在○里填“>”“<”或“=”：{a} ○ {b}", s)
    def diji(r):
        n = r.randint(3, 5); k = r.randint(1, n)
        return Fi(f"{n}个小朋友排成一排，{NAMES[k % 12]}从左数排第{k}个，从右数排第（　）个。", str(n - k + 1))
    return [g_add(0, 5, 5), g_sub(0, 5, minb=0), fen, cmp, diji]

def u1a_2():
    def lian(r):
        a, b, c = r.randint(1, 5), r.randint(1, 4), r.randint(1, 4)
        if a + b + c > 10: return None
        return Fi(f"{a} + {b} + {c} = ？", str(a + b + c))
    def lianjian(r):
        a = r.randint(6, 10); b = r.randint(1, 4); c = r.randint(1, 4)
        if a - b - c < 0: return None
        return Fi(f"{a} - {b} - {c} = ？", str(a - b - c))
    def hunhe(r):
        a, b, c = r.randint(2, 9), r.randint(1, 5), r.randint(1, 5)
        if a + b > 10 or a + b - c < 0: return None
        v = a + b - c
        return C(f"{a} + {b} - {c} = ？", numopts(v, [a + b + c, a - b + c, v + 1, v - 1]))
    def fen(r):
        n = r.randint(6, 10); a = r.randint(1, n - 1)
        return Fi(f"{n}可以分成{a}和（　）。", str(n - a))
    def word(r):
        a, b = r.randint(2, 7), r.randint(1, 3)
        if a + b > 10: return None
        nm = r.choice(NAMES)
        return Fi(f"树上有{a}只小鸟，又飞来了{b}只，现在树上一共有几只小鸟？", str(a + b))
    def word2(r):
        a = r.randint(6, 10); b = r.randint(1, a - 1)
        return Fi(f"盘子里有{a}个桃子，小猴吃掉了{b}个，还剩几个？", str(a - b))
    def diji(r):
        a, b = r.randint(2, 6), r.randint(2, 6)
        return Fi(f"小朋友排队，从前往后数小丽排第{a}，从后往前数她排第{b}，这一队一共有几人？", str(a + b - 1))
    return [g_add(1, 9, 10), g_sub(1, 10), lian, lianjian, hunhe, fen, word, word2, diji]

SOLIDS = {"长方体": ["牙膏盒", "粉笔盒", "冰箱", "砖块", "文具盒", "牛奶盒"],
          "正方体": ["魔方", "骰子", "正方体积木"],
          "圆柱": ["易拉罐", "茶叶罐", "没削的圆铅笔", "圆柱形水杯", "胶水瓶身"],
          "球": ["足球", "乒乓球", "篮球", "玻璃弹珠", "地球仪的球"]}
def u1a_3():
    def which(r):
        s = r.choice(list(SOLIDS)); right = r.choice(SOLIDS[s])
        wrong = [r.choice(SOLIDS[o]) for o in SOLIDS if o != s]
        return C(f"下面哪个物体的形状是{s}？", [right] + wrong)
    def shape_of(r):
        s = r.choice(list(SOLIDS)); it = r.choice(SOLIDS[s])
        return C(f"“{it}”的形状最接近哪种立体图形？", [s] + [o for o in SOLIDS if o != s])
    facts = [("下面的立体图形中，最容易滚动的是（　）。", ["球", "正方体", "长方体", "圆柱"]),
             ("既能滚动，又能平稳地立着的立体图形是（　）。", ["圆柱", "球", "正方体", "长方体"]),
             ("正方体有几个面？", "6"), ("长方体有几个面？", "6"),
             ("正方体的6个面都是什么形状？", ["正方形", "长方形", "三角形", "圆"]),
             ("圆柱的上下两个面是什么形状？", ["圆", "正方形", "长方形", "三角形"])]
    def count(r):
        a, b, c = r.randint(1, 5), r.randint(1, 5), r.randint(1, 5)
        return Fi(f"用积木搭了一座小房子，用了{a}个长方体、{b}个正方体和{c}个圆柱，一共用了几个积木？", str(a + b + c)) if a + b + c <= 10 else None
    return [which, shape_of, fact(facts), count]

def u1a_4():
    def zucheng(r):
        n = r.randint(11, 20)
        if n == 20: return Fi("2个十是（　）。", "20")
        return Fi(f"1个十和{n - 10}个一组成的数是（　）。", str(n))
    def ones(r):
        n = r.randint(11, 19)
        return Fi(f"{n}里面有1个十和（　）个一。", str(n - 10))
    def order(r):
        n = r.randint(11, 19)
        if r.random() < .5: return Fi(f"{n}后面的一个数是（　）。", str(n + 1))
        return Fi(f"{n}前面的一个数是（　）。", str(n - 1))
    def between(r):
        a = r.randint(10, 15); b = a + r.randint(2, 5)
        if b > 20: return None
        return Fi(f"比{a}大、比{b}小的数一共有（　）个。", str(b - a - 1))
    def simple(r):
        a = r.randint(1, 9)
        if r.random() < .5: return Fi(f"10 + {a} = ？", str(10 + a))
        return Fi(f"1{a} - {a} = ？", "10")
    def simple2(r):
        a, b = r.randint(1, 8), r.randint(1, 8)
        if a + b > 9: return None
        if r.random() < .5: return Fi(f"1{a} + {b} = ？", str(10 + a + b))
        return Fi(f"1{a + b} - {b} = ？", str(10 + a))
    def cmp(r):
        a, b = r.randint(11, 20), r.randint(11, 20)
        if a == b: return None
        return C(f"{a}和{b}，哪个数大？", [str(max(a, b)), str(min(a, b)), "一样大", "无法比较"])
    return [zucheng, ones, order, between, simple, simple2, cmp]

def u1a_5():
    def jin(r):
        a = r.randint(2, 9); b = r.randint(2, 9)
        if a + b < 11: return None
        s = a + b; q = f"{a} + {b} = ？"
        if r.random() < .5: return Fi(q, str(s))
        return C(q, numopts(s, [s - 10, s + 1, s - 1, s + 10]))
    def word(r):
        a, b = r.randint(5, 9), r.randint(3, 9)
        if a + b < 11: return None
        obj = r.choice(["只小鸡", "个气球", "朵花", "本书", "条小鱼"])
        return Fi(f"左边有{a}{obj}，右边有{b}{obj}，一共有几{obj[0]}{obj[1:]}？".replace(f"几{obj[0]}{obj[1:]}", f"{obj}"), str(a + b))
    def word2(r):
        a, b = r.randint(6, 9), r.randint(4, 9)
        if a + b < 11: return None
        return Fi(f"{r.choice(NAMES)}先折了{a}只纸鹤，又折了{b}只，一共折了多少只？", str(a + b))
    def missing(r):
        a = r.randint(2, 9); s = r.randint(11, 18)
        if s - a < 2 or s - a > 9: return None
        return Fi(f"{a} + （　） = {s}", str(s - a))
    def cou(r):
        a = r.choice([9, 8, 7]); b = r.randint(3, 9)
        if a + b < 11: return None
        return C(f"用“凑十法”计算{a} + {b}时，先把{b}分成几和几？", [f"{10 - a}和{b - 10 + a}", f"{a}和{b - a}" if b > a else f"1和{b - 1}", f"{b - 10 + a}和{10 - a + 1}", f"5和{b - 5}" if b > 5 else f"2和{b - 2}"])
    return [jin, word2, missing, cou, jin]

def u_review(gens): return [g_mixed_review(gens)] * 3

def vol_g1a():
    U = [("第一单元 5以内数的认识和加、减法", u1a_1()),
         ("第二单元 6～10的认识和加、减法", u1a_2()),
         ("第三单元 认识立体图形", u1a_3()),
         ("第四单元 11～20的认识", u1a_4()),
         ("第五单元 20以内的进位加法", u1a_5())]
    def mix(r):
        a, b, c = r.randint(2, 9), r.randint(2, 9), r.randint(1, 9)
        if a + b > 20 or a + b - c < 0: return None
        return Fi(f"{a} + {b} - {c} = ？", str(a + b - c))
    U.append(("第六单元 复习与关联", [mix, g_add(2, 9, 18, carry=True), g_sub(11, 19, borrow=False)]))
    return U

# =====================================================================
# 1下
# =====================================================================
def u1b_1():
    sides = {"三角形": 3, "长方形": 4, "正方形": 4, "五边形": 5, "六边形": 6}
    def sd(r):
        s = r.choice(list(sides))
        return Fi(f"一个{s}有（　）条边。", str(sides[s]))
    def tot(r):
        a, b = r.choice(list(sides)), r.choice(list(sides))
        m, n = r.randint(1, 3), r.randint(1, 3)
        if a == b: return None
        return Fi(f"{m}个{a}和{n}个{b}一共有（　）条边。", str(m * sides[a] + n * sides[b]))
    facts = [("用两个完全一样的正方形拼成的图形是（　）。", ["长方形", "正方形", "三角形", "圆"]),
             ("正方形的4条边（　）。", ["都相等", "都不相等", "只有2条相等", "只有3条相等"]),
             ("长方形的对边（　）。", ["相等", "不相等", "一长一短", "无法判断"]),
             ("把正方体的一个面描下来，得到的图形是（　）。", ["正方形", "圆", "三角形", "五边形"]),
             ("把圆柱的底面描下来，得到的图形是（　）。", ["圆", "正方形", "长方形", "三角形"]),
             ("沿正方形的一条对角线对折剪开，得到两个（　）。", ["三角形", "长方形", "正方形", "圆"]),
             ("下面图形中没有角的是（　）。", ["圆", "三角形", "长方形", "正方形"]),
             ("用4根同样长的小棒可以围成一个（　）。", ["正方形", "三角形", "圆", "五边形"])]
    def sticks(r):
        n = r.randint(2, 5)
        return Fi(f"用小棒摆三角形，摆{n}个分开的三角形需要（　）根小棒。", str(3 * n))
    return [sd, tot, fact(facts), sticks]

def u1b_2():
    def tui(r):
        a = r.randint(11, 18); b = r.randint(2, 9)
        if a % 10 >= b or a - b < 2: return None
        d = a - b; q = f"{a} - {b} = ？"
        if r.random() < .55: return Fi(q, str(d))
        return C(q, numopts(d, [b - a % 10 + 10 - 10 + (b - a % 10), d + 1, d - 1, 10 - b, d + 10]))
    def word(r):
        a = r.randint(11, 18); b = r.randint(3, 9)
        if a % 10 >= b: return None
        return Fi(f"停车场有{a}辆车，开走了{b}辆，还剩几辆？", str(a - b))
    def missing(r):
        a = r.randint(11, 18); d = r.randint(2, 9)
        b = a - d
        if not (2 <= b <= 9) or a % 10 >= b: return None
        return Fi(f"{a} - （　） = {d}", str(b))
    def pofa(r):
        a = r.randint(11, 18); b = r.randint(2, 9)
        if a % 10 >= b: return None
        return Fi(f"用“破十法”算{a} - {b}：先算10 - {b} = （　）。", str(10 - b))
    return [tui, word, missing, pofa]

def u1b_3():
    def zu(r):
        t, o = r.randint(1, 9), r.randint(0, 9)
        return Fi(f"{t}个十和{o}个一组成的数是（　）。", str(t * 10 + o))
    def wei(r):
        n = r.randint(11, 99)
        if r.random() < .5: return Fi(f"{n}的十位上是（　）。", str(n // 10))
        return Fi(f"{n}的个位上是（　）。", str(n % 10))
    def order(r):
        n = r.randint(20, 99)
        return Fi(f"和{n}相邻的两个数是（　）和（　）（从小到大，用顿号隔开）。", [f"{n - 1}、{n + 1}", f"{n - 1},{n + 1}", f"{n - 1}，{n + 1}", f"{n - 1} {n + 1}"])
    def zheng(r):
        a, b = r.randint(1, 9) * 10, r.randint(1, 9) * 10
        if r.random() < .5:
            if a + b > 100: return None
            return Fi(f"{a} + {b} = ？", str(a + b))
        if a < b: a, b = b, a
        return Fi(f"{a} - {b} = ？", str(a - b))
    def zj(r):
        a, b = r.randint(1, 9) * 10, r.randint(1, 9)
        if r.random() < .5: return Fi(f"{a} + {b} = ？", str(a + b))
        return Fi(f"{a + b} - {b} = ？", str(a))
    def big(r):
        n = r.randint(30, 60)
        opts = [str(n + r.randint(40, 39 + (100 - n) if 100 - n > 40 else 41)), str(n + 2), str(n - 1), str(n + 5)]
        if int(opts[0]) > 100: return None
        return C(f"下面哪个数比{n}“大得多”？", opts)
    def cnt(r):
        a = r.randint(20, 80); b = a + r.randint(3, 9)
        return Fi(f"从{a}数到{b}，一共数了（　）个数。", str(b - a + 1))
    return [zu, wei, order, zheng, zj, big, cnt]

def u1b_4():
    return [g_add(10, 89, 99, carry=False), g_add(2, 89, 99, carry=True),
            g_sub(20, 99, borrow=False), g_sub(20, 99, borrow=True),
            lambda r: (lambda a, b: Fi(f"{a} + {b * 10} = ？", str(a + b * 10)) if a + b * 10 < 100 else None)(r.randint(11, 69), r.randint(1, 3)),
            lambda r: (lambda a, b, c: Fi(f"{a} - {b} - {c} = ？", str(a - b - c)) if a - b - c >= 0 else None)(r.randint(30, 60), r.randint(5, 15), r.randint(5, 15))]

def u1b_5():
    def word(r):
        a, b = r.randint(23, 58), r.randint(15, 39)
        if a + b > 99: return None
        return Fi(f"一年级一班有{a}本书，二班有{b}本书，两个班一共有多少本书？", str(a + b))
    def word2(r):
        a = r.randint(50, 96); b = r.randint(18, a - 5)
        return Fi(f"图书角原有{a}本书，借出去{b}本，还剩多少本？", str(a - b))
    return [g_add(11, 79, 99, carry=True, fillp=.5), g_sub(31, 99, borrow=True, fillp=.5, minb=11),
            g_add(11, 79, 99, carry=False), g_sub(31, 99, borrow=False, minb=11), word, word2]

def u1b_6():
    def more(r):
        a, d = r.randint(15, 60), r.randint(3, 25)
        if a + d > 99: return None
        return Fi(f"红花有{a}朵，黄花比红花多{d}朵，黄花有多少朵？", str(a + d))
    def less(r):
        a, d = r.randint(25, 80), r.randint(3, 20)
        return Fi(f"小明有{a}张卡片，小华比小明少{d}张，小华有多少张？", str(a - d))
    def diff(r):
        a, b = r.randint(20, 90), r.randint(10, 80)
        if a <= b: return None
        return Fi(f"男生有{a}人，女生有{b}人，男生比女生多多少人？", str(a - b))
    def trap(r):
        a, d = r.randint(20, 60), r.randint(5, 15)
        return C(f"哥哥有{a}元，比弟弟多{d}元，弟弟有多少元？", numopts(a - d, [a + d, d, a]))
    def two(r):
        a, d1, d2 = r.randint(20, 40), r.randint(5, 15), r.randint(3, 12)
        b = a + d1
        return Fi(f"一班种树{a}棵，二班比一班多种{d1}棵，三班比二班少种{d2}棵，三班种了多少棵？", str(b - d2))
    return [more, less, diff, trap, two]

def u1b_money():
    def yuan2jiao(r):
        y, j = r.randint(1, 9), r.randint(0, 9)
        if j == 0: return Fi(f"{y}元 = （　）角", str(y * 10))
        return Fi(f"{y}元{j}角 = （　）角", str(y * 10 + j))
    def jiao2yuan(r):
        n = r.randint(11, 99)
        y, j = divmod(n, 10)
        if j == 0: return None
        return C(f"{n}角 = （　）", [f"{y}元{j}角", f"{j}元{y}角", f"{n}元", f"{y}元"])
    def change(r):
        y, j = r.randint(1, 8), r.randint(1, 9); pay = r.choice([10, 20]) if y >= 5 else r.choice([5, 10])
        price = y * 10 + j; ch = pay * 10 - price
        cy, cj = divmod(ch, 10)
        right = f"{cy}元{cj}角" if cj else f"{cy}元"
        if cy == 0: right = f"{cj}角"
        w1 = f"{cy + 1}元{cj}角"; w2 = f"{cy}元{10 - cj}角" if cj else f"{cy - 1}元"; w3 = f"{cy}元{(cj + 1) % 10}角"
        return C(f"一个文具标价{y}元{j}角，付了{pay}元，应找回多少钱？", [right, w1, w2, w3])
    facts = [("1元 = （　）角", "10"), ("1角 = （　）分", "10"),
             ("下面最大的人民币是（　）。", ["100元", "50元", "20元", "10元"])]
    def buy(r):
        a, b = r.randint(2, 6), r.randint(2, 6)
        return Fi(f"一支铅笔{a}元，一块橡皮{b}元，买一支铅笔和一块橡皮一共要（　）元。", str(a + b))
    return [yuan2jiao, jiao2yuan, change, fact(facts), buy]

def vol_g1b():
    U = [("第一单元 认识平面图形", u1b_1()), ("第二单元 20以内的退位减法", u1b_2()),
         ("第三单元 100以内数的认识", u1b_3()), ("第四单元 100以内的口算加、减法", u1b_4()),
         ("第五单元 100以内的笔算加、减法", u1b_5()), ("第六单元 数量间的加减关系", u1b_6()),
         ("综合与实践 欢乐购物街（认识人民币）", u1b_money())]
    U.append(("第七单元 复习与关联", [g_add(11, 79, 99), g_sub(20, 99), g_sub(11, 18, borrow=True)]))
    return U

# =====================================================================
# 2上
# =====================================================================
COLORS = ["红", "黄", "蓝", "绿", "白"]
def u2a_1():
    def most(r):
        cs = r.sample(COLORS, 3); ns = r.sample(range(2, 15), 3)
        i = ns.index(max(ns))
        return C(f"盒子里有{cs[0]}球{ns[0]}个、{cs[1]}球{ns[1]}个、{cs[2]}球{ns[2]}个。哪种颜色的球最多？", [cs[i] + "球"] + [c + "球" for j, c in enumerate(cs) if j != i] + ["一样多"])
    def total(r):
        ns = [r.randint(3, 15) for _ in range(3)]
        return Fi(f"按形状分类：三角形{ns[0]}个，圆{ns[1]}个，正方形{ns[2]}个。一共有多少个图形？", str(sum(ns)))
    def diff(r):
        a, b = r.randint(10, 30), r.randint(3, 9)
        return Fi(f"调查最喜欢的水果：喜欢苹果的有{a}人，喜欢香蕉的比苹果少{b}人。喜欢香蕉的有多少人？", str(a - b))
    def least(r):
        cs = ["跳绳", "踢毽子", "拍球", "跑步"]; ns = r.sample(range(3, 20), 4); i = ns.index(min(ns))
        return C("统计同学们最喜欢的运动：" + "，".join(f"{c}{n}人" for c, n in zip(cs, ns)) + "。喜欢哪项运动的人最少？", [cs[i]] + [c for j, c in enumerate(cs) if j != i])
    return [most, total, diff, least]

def u2a_2():
    def rep(r):
        a, b = r.randint(2, 6), r.randint(2, 6)
        return C(f"{b}个{a}相加，用乘法算式表示是（　）。", [f"{a} × {b}", f"{a} + {b}", f"{a} × {a}", f"{b} + {b}"] if a != b else [f"{a} × {b}", f"{a} + {b}", f"{a} × {a + 1}", f"{a} + {a}"])
    def kj(r):
        a, b = sorted([r.randint(1, 6), r.randint(1, 6)])
        return Fi(f"乘法口诀“{CN[a]}{CN[b]}（　）”中，括号里应填的数是？", str(a * b))
    def chengjia(r):
        a, b, c = r.randint(2, 6), r.randint(2, 6), r.randint(1, 9)
        if r.random() < .5:
            v = a * b + c
            return C(f"{a} × {b} + {c} = ？", numopts(v, [a * (b + c), a + b + c, v + 1, v - 1]))
        if a * b - c < 0: return None
        return Fi(f"{a} × {b} - {c} = ？", str(a * b - c))
    def word(r):
        a, b = r.randint(2, 6), r.randint(2, 6)
        return Fi(f"每盘放{a}个苹果，{b}盘一共放多少个苹果？", str(a * b))
    def buy(r):
        a, b = r.randint(2, 6), r.randint(2, 6)
        return Fi(f"一个本子{a}元，买{b}个这样的本子要多少元？", str(a * b))
    return [g_mul(1, 6, 1, 6), rep, kj, chengjia, word, buy]

def u2a_3():
    def ping(r):
        d, qt = r.randint(2, 6), r.randint(2, 6)
        return Fi(f"把{d * qt}个桃子平均分给{d}只小猴，每只小猴分到几个？", str(qt))
    def bao(r):
        d, qt = r.randint(2, 6), r.randint(2, 6)
        return Fi(f"有{d * qt}个苹果，每{d}个装一袋，可以装几袋？", str(qt))
    def name(r):
        d, qt = r.randint(2, 6), r.randint(2, 6)
        return C(f"在{d * qt} ÷ {d} = {qt}中，{d}叫作（　）。", ["除数", "被除数", "商", "因数"])
    def kj(r):
        d, qt = r.randint(2, 6), r.randint(2, 6)
        a, b = sorted([d, qt])
        return C(f"计算{d * qt} ÷ {d}时，用的乘法口诀是（　）。", [f"{CN[a]}{CN[b]}{num_cn(a * b)}", f"{CN[a]}{CN[b + 1] if b < 9 else CN[b]}{num_cn(a * (b + 1))}", f"{CN[max(a - 1, 1)]}{CN[b]}{num_cn(max(a - 1, 1) * b)}", f"{CN[a]}{CN[min(b + 2, 9)]}{num_cn(a * min(b + 2, 9))}"])
    return [g_div(2, 6, 1, 6), ping, bao, name, kj]

def num_cn(n):
    if n == 10: return "一十"
    if n < 10: return ("得" + CN[n])
    t, o = divmod(n, 10)
    return (CN[t] if t > 1 else "") + "十" + (CN[o] if o else "")

def u2a_dir():
    dirs = ["东", "南", "西", "北"]
    def left(r):
        i = r.randint(0, 3); f = dirs[i]
        # facing f; right is clockwise (东->南), left counterclockwise
        rgt, lft, back = dirs[(i + 1) % 4], dirs[(i - 1) % 4], dirs[(i + 2) % 4]
        k = r.choice(["左边", "右边", "后面"])
        ans = {"左边": lft, "右边": rgt, "后面": back}[k]
        return C(f"面向{f}站立，你的{k}是（　）面。", [ans] + [d for d in dirs if d != ans])
    facts = [("早晨面对太阳，你的后面是（　）面。", ["西", "东", "南", "北"]),
             ("太阳从（　）方升起。", ["东", "西", "南", "北"]),
             ("地图上通常是“上北下南，左（　）右东”。", ["西", "北", "南", "东"]),
             ("与“东”相对的方向是（　）。", ["西", "南", "北", "东北"]),
             ("与“南”相对的方向是（　）。", ["北", "东", "西", "西南"])]
    return [left, fact(facts)]

def u2a_4():
    def conv(r):
        m = r.randint(1, 9)
        if r.random() < .5: return Fi(f"{m}米 = （　）厘米", str(m * 100))
        return Fi(f"{m * 100}厘米 = （　）米", str(m))
    def mix(r):
        m, c = r.randint(1, 3), r.randint(10, 90)
        return Fi(f"{m}米 - {c}厘米 = （　）厘米", str(m * 100 - c))
    def unit(r):
        items = [("一支铅笔长约18", "厘米"), ("教室门高约2", "米"), ("小明身高约130", "厘米"), ("一棵大树高约10", "米"),
                 ("数学书宽约19", "厘米"), ("黑板长约4", "米"), ("一块橡皮长约4", "厘米"), ("操场跑道一圈长约200", "米")]
        q, a = r.choice(items)
        return C(f"{q}（　）。", [a, "米" if a == "厘米" else "厘米", "分", "元"])
    def ruler(r):
        a = r.randint(0, 6); b = a + r.randint(2, 9)
        return C(f"用直尺量一根小棒，左端对着刻度{a}，右端对着刻度{b}，小棒长（　）厘米。", numopts(b - a, [b, a + b, b - a + 1]))
    def cmp(r):
        m, c = r.randint(1, 3), r.randint(101, 350)
        big = "前者长" if m * 100 > c else "后者长" if m * 100 < c else "一样长"
        if m * 100 == c: return None
        return C(f"{m}米和{c}厘米比较，（　）。", [big, "后者长" if big == "前者长" else "前者长", "一样长", "无法比较"])
    facts = [("线段有（　）个端点。", "2"), ("把线段的两端无限延长，就得到一条（　）。", ["直线", "射线", "线段", "曲线"])]
    return [conv, mix, unit, ruler, cmp, fact(facts)]

def u2a_5():
    def word(r):
        a, b = r.randint(7, 9), r.randint(2, 9)
        return Fi(f"每排坐{a}人，{b}排一共坐多少人？", str(a * b))
    def word2(r):
        d, qt = r.randint(7, 9), r.randint(2, 9)
        return Fi(f"{d * qt}朵花，平均插在{d}个花瓶里，每个花瓶插几朵？", str(qt))
    def two(r):
        a, b, c = r.randint(7, 9), r.randint(2, 9), r.randint(3, 20)
        return Fi(f"每盒彩笔有{a}支，买了{b}盒，又送了{c}支，一共有多少支彩笔？", str(a * b + c))
    def kj(r):
        a, b = sorted([r.randint(2, 9), r.choice([7, 8, 9])])
        return Fi(f"乘法口诀“{CN[a]}{CN[b]}（　）”中，括号里应填的数是？", str(a * b))
    return [g_mul(7, 9, 2, 9), g_div(7, 9, 2, 9), word, word2, two, kj]

def vol_g2a():
    U = [("第一单元 分类与整理", u2a_1()), ("第二单元 1～6的表内乘法", u2a_2()),
         ("第三单元 1～6的表内除法", u2a_3()), ("综合与实践 校园小导游", u2a_dir()),
         ("第四单元 厘米和米", u2a_4()), ("第五单元 7～9的表内乘、除法", u2a_5()),
         ("第六单元 复习与关联", [g_mul(2, 9, 2, 9), g_div(2, 9, 2, 9), g_add(10, 60, 99)])]
    return U

# =====================================================================
# 2下
# =====================================================================
def hm(h, m): return f"{h}:{m:02d}"
def u2b_time():
    def after(r):
        h, m = r.randint(7, 10), r.choice([0, 10, 15, 20, 30, 40, 45]); d = r.choice([15, 20, 25, 30, 35, 40, 50])
        t = h * 60 + m + d; nh, nm = divmod(t, 60)
        return Fi(f"{hm(h, m)}开始上课，经过{d}分钟后是几时几分？（如 9:05）", [hm(nh, nm), f"{nh}时{nm}分" if nm else f"{nh}时", f"{nh}:{nm:02d}"])
    def read(r):
        h, m = r.randint(1, 11), r.choice([5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55])
        return C(f"钟面上时针指在{h}和{h + 1}之间，分针指着{m // 5}，这时是（　）。", [f"{h}:{m:02d}", f"{h + 1}:{m:02d}", f"{h}:{(m // 5):02d}", f"{m // 5}:{h * 5 % 60:02d}"])
    facts = [("1时 = （　）分", "60"), ("分针走1小格是（　）分。", "1"), ("分针走1大格是（　）分。", "5"),
             ("时针从12走到3，经过了（　）时。", "3"), ("分针从12走到6，经过了（　）分。", "30")]
    def conv(r):
        h, m = r.randint(1, 3), r.randint(5, 55)
        return Fi(f"{h}时{m}分 = （　）分", str(h * 60 + m))
    return [after, read, fact(facts), conv]

def u2b_1():
    def calc(r):
        d = r.randint(2, 9); qt = r.randint(1, 9); rem = r.randint(1, d - 1) if d > 1 else 0
        n = d * qt + rem
        return Fi(f"{n} ÷ {d} = （　）……（　）（格式：商……余数）", [f"{qt}……{rem}", f"{qt}...{rem}", f"{qt}…{rem}", f"{qt}余{rem}"])
    def remc(r):
        d = r.randint(3, 9)
        return C(f"一个数除以{d}，余数最大是（　）。", numopts(d - 1, [d, d + 1, 1]))
    def boats(r):
        cap = r.randint(3, 6); n = cap * r.randint(3, 8) + r.randint(1, cap - 1)
        return C(f"{n}名同学去划船，每条船最多坐{cap}人，至少需要几条船？", numopts(n // cap + 1, [n // cap, n // cap + 2, n % cap]))
    def most(r):
        cap = r.randint(3, 8); n = cap * r.randint(3, 9) + r.randint(1, cap - 1)
        return C(f"有{n}元，每本笔记本{cap}元，最多能买几本？", numopts(n // cap, [n // cap + 1, n % cap, n // cap - 1]))
    def rem(r):
        d = r.randint(2, 9); qt = r.randint(2, 9); rm = r.randint(1, d - 1) if d > 2 else 1
        n = d * qt + rm
        return Fi(f"{n}个苹果，每{d}个装一盘，可以装{qt}盘，还剩（　）个。", str(rm))
    return [calc, remc, boats, most, rem]

def u2b_2():
    def times(r):
        b, k = r.randint(2, 9), r.randint(2, 9)
        return Fi(f"{b * k}是{b}的（　）倍。", str(k))
    def big(r):
        b, k = r.randint(2, 9), r.randint(2, 9)
        return Fi(f"黄花有{b}朵，红花的朵数是黄花的{k}倍，红花有多少朵？", str(b * k))
    def small(r):
        b, k = r.randint(2, 9), r.randint(2, 9)
        return C(f"红花有{b * k}朵，是黄花的{k}倍，黄花有多少朵？", numopts(b, [b * k * k, b * k - k, b * k + k]))
    def share(r):
        d, qt = r.randint(2, 9), r.randint(2, 9)
        return Fi(f"老师买来{d * qt}本书，平均分给{d}个小组，每组分得几本？", str(qt))
    def price(r):
        p, n = r.randint(2, 9), r.randint(2, 9)
        return Fi(f"买{n}个同样的足球共花{p * n * 10}元，每个足球多少元？", str(p * 10))
    return [times, big, small, share, price]

def u2b_3():
    def zu(r):
        a, b, c, d = r.randint(1, 9), r.randint(0, 9), r.randint(0, 9), r.randint(0, 9)
        parts = [f"{a}个千"] + ([f"{b}个百"] if b else []) + ([f"{c}个十"] if c else []) + ([f"{d}个一"] if d else [])
        return Fi("由" + "、".join(parts) + "组成的数是（　）。", str(a * 1000 + b * 100 + c * 10 + d))
    def read(r):
        n = r.choice([r.randint(1000, 9999), r.randint(1, 9) * 1000 + r.randint(0, 9) * 10 + r.randint(0, 9), r.randint(100, 999)])
        return C(f"{n}的最高位是（　）位。", ["千" if n >= 1000 else "百", "百" if n >= 1000 else "千", "十", "万"])
    def near(r):
        n = r.randint(101, 999)
        if n % 100 == 50 or n % 100 == 0: return None
        a = round(n / 100) * 100
        return C(f"{n}最接近哪个整百数？", numopts(a, [a + 100, a - 100, n // 10 * 10]))
    def cmp(r):
        a, b = r.randint(1000, 9999), r.randint(1000, 9999)
        if a == b: return None
        return Fi(f"在○里填“>”或“<”：{a} ○ {b}", ">" if a > b else "<")
    def wan(r):
        k = r.randint(1, 9)
        return Fi(f"{k}个千是（　）。", str(k * 1000)) if r.random() < .5 else Fi("10个一千是（　）。", "10000")
    def jian(r):
        a, b = r.randint(1, 9) * 1000, r.randint(1, 9) * 100
        if r.random() < .5: return Fi(f"{a} + {b} = ？", str(a + b))
        return Fi(f"{a + b} - {a} = ？", str(b))
    return [zu, read, near, cmp, wan, jian]

def u2b_4():
    def add3(r):
        a, b = r.randint(100, 899), r.randint(100, 899)
        if a + b > 9999: return None
        s = a + b; q = f"{a} + {b} = ？"
        if r.random() < .5: return Fi(q, str(s))
        wrong = (a % 10 + b % 10) % 10 + ((a // 10 % 10 + b // 10 % 10) % 10) * 10 + (a // 100 + b // 100) * 100
        return C(q, numopts(s, [wrong, s + 10, s - 10, s + 100]))
    def sub3(r):
        a = r.randint(300, 999); b = r.randint(100, a - 1)
        d = a - b; q = f"{a} - {b} = ？"
        if r.random() < .5: return Fi(q, str(d))
        return C(q, numopts(d, [d + 10, d - 10, d + 100, a + b]))
    def zb(r):
        a, b = r.randint(1, 9) * 100, r.randint(1, 9) * 100
        if r.random() < .5: return Fi(f"{a} + {b} = ？", str(a + b))
        if a < b: a, b = b, a
        return Fi(f"{a} - {b} = ？", str(a - b))
    def est(r):
        a, b = r.randint(101, 499), r.randint(101, 499)
        if a % 100 in (50,) or b % 100 in (50,): return None
        ea, eb = round(a / 100) * 100, round(b / 100) * 100
        return C(f"估算：{a} + {b}大约是多少？（把每个数看成最接近的整百数）", numopts(ea + eb, [ea + eb + 100, ea + eb - 100, a + b]))
    def rel(r):
        a, b = r.randint(100, 500), r.randint(100, 400)
        return C(f"已知 {a} + {b} = {a + b}，那么 {a + b} - {a} = （　）。", numopts(b, [a, a + b, b + 10]))
    def word(r):
        a, b = r.randint(150, 600), r.randint(120, 380)
        return Fi(f"学校图书馆有故事书{a}本，科技书比故事书多{b}本，科技书有多少本？", str(a + b))
    return [add3, sub3, zb, est, rel, word]

def vol_g2b():
    return [("综合与实践 时间在哪里", u2b_time()), ("第一单元 有余数的除法", u2b_1()),
            ("第二单元 数量间的乘除关系", u2b_2()), ("第三单元 万以内数的认识", u2b_3()),
            ("第四单元 万以内的加法和减法", u2b_4()),
            ("第五单元 复习与关联", [g_mul(2, 9, 2, 9), g_div(2, 9, 2, 9), u2b_4()[0], u2b_1()[0]])]

# =====================================================================
# 3上
# =====================================================================
def u3a_1():
    facts = [("从任意一个面看正方体，看到的形状都是（　）。", ["正方形", "长方形", "三角形", "圆"]),
             ("从上面看一个立着的圆柱形水杯，看到的形状是（　）。", ["圆", "长方形", "正方形", "三角形"]),
             ("从正面看一个立着的圆柱形水杯，看到的形状是（　）。", ["长方形", "圆", "三角形", "梯形"]),
             ("一个正方体的展开图由（　）个正方形组成。", "6"),
             ("从不同方向观察同一个物体，看到的形状（　）。", ["可能不同", "一定相同", "一定不同", "都是正方形"]),
             ("从任何方向看一个球，看到的形状都是（　）。", ["圆", "正方形", "长方形", "椭圆以外的图形"])]
    def row(r):
        n = r.randint(2, 6)
        return Fi(f"把{n}个同样的小正方体排成一排放在桌上，从正面看能看到（　）个正方形。", str(n))
    def row2(r):
        n = r.randint(2, 6)
        return Fi(f"把{n}个同样的小正方体排成一排放在桌上（从左往右排），从左面看能看到（　）个正方形。", "1")
    def stack(r):
        a, b = r.randint(2, 4), r.randint(2, 4)
        return Fi(f"用小正方体摆成{a}行{b}列的一层长方形，从上面看能看到（　）个正方形。", str(a * b))
    return [fact(facts), row, row2, stack]

def u3a_2():
    def mix1(r):
        a, b, c = r.randint(10, 60), r.randint(2, 9), r.randint(2, 9)
        v = a + b * c
        return C(f"{a} + {b} × {c} = ？", numopts(v, [(a + b) * c, v + 1, a * b + c, v - b]))
    def mix2(r):
        a, b, c = r.randint(2, 9), r.randint(2, 9), r.randint(10, 40)
        return Fi(f"({c} + {a}) × {b} = ？", str((c + a) * b))
    def mix3(r):
        c, qt = r.randint(2, 9), r.randint(2, 9); b = c * qt; a = r.randint(qt + 1, 80)
        v = a - b // c
        return C(f"{a} - {b} ÷ {c} = ？", numopts(v, [(a - b) // c if (a - b) % c == 0 and a > b else v + 2, v - 1, v + 1, a - b + c]))
    def mix4(r):
        d, qt = r.randint(2, 9), r.randint(2, 9); s = d * qt; a = r.randint(1, s - 1)
        return Fi(f"({a} + {s - a}) ÷ {d} = ？", str(qt))
    def word(r):
        p, n, pay = r.randint(3, 9), r.randint(2, 6), 50
        if p * n >= pay: return None
        return Fi(f"一本笔记本{p}元，买{n}本，付了{pay}元，应找回多少元？（列综合算式计算）", str(pay - p * n))
    def word2(r):
        total, used, d = r.randint(60, 100), r.randint(10, 30), r.randint(2, 6)
        if (total - used) % d: return None
        return Fi(f"一根绳子长{total}米，先剪去{used}米，剩下的平均分成{d}段，每段长多少米？", str((total - used) // d))
    return [mix1, mix2, mix3, mix4, word, word2]

def u3a_3():
    def conv(r):
        t = r.choice(["mm", "dm", "km", "mmcm", "dmcm"])
        k = r.randint(2, 9)
        if t == "mm": return Fi(f"{k}厘米 = （　）毫米", str(k * 10))
        if t == "dm": return Fi(f"{k}米 = （　）分米", str(k * 10))
        if t == "km": return Fi(f"{k}千米 = （　）米", str(k * 1000))
        if t == "mmcm": return Fi(f"{k * 10}毫米 = （　）厘米", str(k))
        return Fi(f"{k}分米 = （　）厘米", str(k * 10))
    def unit(r):
        items = [("一枚1元硬币厚约2", "毫米"), ("一张课桌高约7", "分米"), ("北京到天津的铁路长约120", "千米"),
                 ("一支粉笔长约8", "厘米"), ("一辆汽车每小时行驶约80", "千米"), ("一块橡皮厚约1", "厘米"),
                 ("一根跳绳长约2", "米"), ("一扇门宽约9", "分米"), ("一张银行卡厚约1", "毫米")]
        q, a = r.choice(items)
        return C(f"{q}（　）。", [a] + [u for u in ["毫米", "厘米", "分米", "米", "千米"] if u != a][:3])
    def mix(r):
        a, b = r.randint(1, 5), r.randint(100, 900)
        return Fi(f"{a}千米 - {b}米 = （　）米", str(a * 1000 - b))
    def mix2(r):
        a, b = r.randint(1, 9), r.randint(1, 9)
        return Fi(f"{a}分米{b}厘米 = （　）厘米", str(a * 10 + b))
    def run(r):
        lap = r.choice([200, 250, 400, 500]); n = 1000 // lap
        return Fi(f"学校跑道一圈是{lap}米，跑（　）圈正好是1千米。", str(n))
    return [conv, unit, mix, mix2, run]

def u3a_mass():
    def conv(r):
        k = r.randint(2, 9)
        t = r.choice(["t", "kg", "g2kg"])
        if t == "t": return Fi(f"{k}吨 = （　）千克", str(k * 1000))
        if t == "kg": return Fi(f"{k}千克 = （　）克", str(k * 1000))
        return Fi(f"{k * 1000}克 = （　）千克", str(k))
    def unit(r):
        items = [("一头大象重约5", "吨"), ("一个鸡蛋重约50", "克"), ("一名三年级学生体重约30", "千克"),
                 ("一袋大米重约10", "千克"), ("一辆卡车载重约4", "吨"), ("一个苹果重约200", "克"), ("一枚1元硬币重约6", "克")]
        q, a = r.choice(items)
        return C(f"{q}（　）。", [a] + [u for u in ["克", "千克", "吨", "千米"] if u != a])
    def truck(r):
        cap = r.randint(2, 5); n = r.randint(3, 8); w = r.randint(cap * n * 1000 - 3000 if cap * n > 3 else 1000, cap * n * 1000)
        trips = -(-w // (cap * 1000))
        return C(f"一辆货车每次最多运{cap}吨，要运{w}千克货物，至少要运几次？", numopts(trips, [w // (cap * 1000), trips + 1, trips + 2]))
    def mix(r):
        a, b = r.randint(1, 5), r.randint(100, 900)
        return Fi(f"{a}千克 - {b}克 = （　）克", str(a * 1000 - b))
    return [conv, unit, truck, mix]

def u3a_4():
    def oral(r):
        a, b = r.randint(2, 9) * r.choice([10, 100]), r.randint(2, 9)
        return Fi(f"{a} × {b} = ？", str(a * b))
    def written(r):
        a, b = r.randint(12, 999), r.randint(2, 9)
        p = a * b; q = f"{a} × {b} = ？"
        if r.random() < .5: return Fi(q, str(p))
        return C(q, numopts(p, [p - b * 10 if a > 10 else p + 1, p + b * 10, p + 10, a * (b + 1)]))
    def zero(r):
        a = r.randint(1, 9) * 100 + r.randint(1, 9); b = r.randint(2, 9)
        return Fi(f"{a} × {b} = ？（中间有0的乘法）", str(a * b))
    def word(r):
        p, n = r.randint(12, 85), r.randint(3, 9)
        return Fi(f"一套故事书{p}元，学校买了{n}套，一共要付多少元？", str(p * n))
    def word2(r):
        v, t = r.randint(45, 120), r.randint(2, 6)
        return Fi(f"一辆汽车每小时行驶{v}千米，{t}小时行驶多少千米？", str(v * t))
    def est(r):
        a, b = r.randint(21, 98), r.randint(3, 9)
        if a % 10 == 5: return None
        ea = round(a / 10) * 10
        return C(f"估算{a} × {b}，结果大约是（　）。", numopts(ea * b, [a * b, ea * b + 100, ea * (b + 1)]))
    def guiyi(r):
        n1, tot, n2 = r.randint(2, 6), None, r.randint(3, 9)
        p = r.randint(3, 15); tot = n1 * p
        return Fi(f"买{n1}支钢笔用了{tot}元，照这样计算，买{n2}支同样的钢笔要多少元？", str(p * n2))
    return [oral, written, zero, word, word2, est, guiyi]

def u3a_code():
    facts = [("我国公民的身份证号码一共有（　）位。", "18"),
             ("身份证号码中，倒数第二位是单数（奇数）表示（　）。", ["男性", "女性", "出生年份", "出生地"]),
             ("我国的邮政编码由（　）位数字组成。", "6"),
             ("身份证号码的第7～14位表示（　）。", ["出生日期", "顺序码", "地址码", "校验码"]),
             ("火警电话是（　）。", ["119", "110", "120", "122"]),
             ("急救电话是（　）。", ["120", "119", "110", "114"])]
    def birth(r):
        y, m, d = r.randint(2014, 2019), r.randint(1, 12), r.randint(1, 28)
        return Fi(f"某人身份证号码第7～14位是{y}{m:02d}{d:02d}，他出生在（　）年。", str(y))
    return [fact(facts), birth]

def u3a_5():
    facts = [("线段有（　）个端点。", "2"), ("射线有（　）个端点。", "1"), ("直线有（　）个端点。", "0"),
             ("经过一点可以画（　）条直线。", ["无数", "1", "2", "3"]),
             ("经过两点可以画（　）条直线。", ["1", "2", "无数", "0"]),
             ("一个直角是（　）度。", "90"),
             ("比直角小的角叫作（　）。", ["锐角", "钝角", "平角", "周角"]),
             ("比直角大、比平角小的角叫作（　）。", ["钝角", "锐角", "直角", "周角"]),
             ("角的大小与（　）有关。", ["两条边张开的大小", "边的长短", "顶点的位置", "画的粗细"]),
             ("钟面上3时整，时针和分针组成的角是（　）。", ["直角", "锐角", "钝角", "平角"]),
             ("钟面上1时整，时针和分针组成的角是（　）。", ["锐角", "直角", "钝角", "平角"]),
             ("钟面上5时整，时针和分针组成的角是（　）。", ["钝角", "锐角", "直角", "平角"])]
    def corners(r):
        s = r.choice([("三角形", 3), ("长方形", 4), ("正方形", 4), ("五边形", 5), ("六边形", 6)])
        return Fi(f"一个{s[0]}有（　）个角。", str(s[1]))
    def cut(r):
        return C("一张长方形纸，剪去一个角（沿直线剪），剩下的部分可能有几个角？", ["3个、4个或5个", "只有3个", "只有5个", "只有4个"])
    def zhijiao(r):
        n = r.randint(2, 4)
        return Fi(f"一副三角尺中，用{n}个直角拼在一起（顶点重合、依次相邻），一共是（　）度。", str(90 * n)) if n < 4 else Fi("4个直角拼成一个周角，是（　）度。", "360")
    return [fact(facts), corners, cut, zhijiao]

def u3a_6():
    def name(r):
        n, k = r.randint(2, 12), None
        k = r.randint(1, n - 1)
        return Fi(f"把一个蛋糕平均分成{n}份，吃了{k}份，吃了这个蛋糕的几分之几？", [f"{k}/{n}"])
    def add(r):
        n = r.randint(3, 12); a = r.randint(1, n - 1); b = r.randint(1, n - a)
        s = F(a + b, n)
        q = f"{a}/{n} + {b}/{n} = ？"
        return C(q, [f"{a + b}/{n}" if a + b < n else "1", f"{a + b}/{2 * n}", f"{a * b}/{n}", f"{a + b + 1}/{n}" if a + b + 1 <= n else f"{a}/{n}"])
    def sub(r):
        n = r.randint(3, 12); a = r.randint(2, n); b = r.randint(1, a - 1)
        q = f"{a}/{n} - {b}/{n} = ？" if a < n else f"1 - {b}/{n} = ？"
        return Fi(q, [f"{a - b}/{n}"])
    def cmp1(r):
        n1, n2 = r.sample(range(2, 10), 2)
        return C(f"1/{n1}和1/{n2}，哪个大？", [f"1/{min(n1, n2)}", f"1/{max(n1, n2)}", "一样大", "无法比较"])
    def cmp2(r):
        n = r.randint(5, 12); a, b = r.sample(range(1, n), 2)
        return C(f"{a}/{n}和{b}/{n}，哪个大？", [f"{max(a, b)}/{n}", f"{min(a, b)}/{n}", "一样大", "无法比较"])
    def part(r):
        n = r.randint(2, 6); k = r.randint(1, n - 1); m = r.randint(2, 6)
        tot = n * m
        return Fi(f"有{tot}个苹果，平均分成{n}份，{k}份是几个？（即{tot}的{k}/{n}）", str(m * k))
    def one(r):
        n = r.randint(2, 10)
        return Fi(f"1里面有（　）个1/{n}。", str(n))
    return [name, add, sub, cmp1, cmp2, part, one]

def vol_g3a():
    return [("第一单元 观察物体", u3a_1()), ("第二单元 混合运算", u3a_2()),
            ("第三单元 毫米、分米和千米", u3a_3()), ("综合与实践 曹冲称象的故事（质量单位）", u3a_mass()),
            ("第四单元 多位数乘一位数", u3a_4()), ("综合与实践 数字编码", u3a_code()),
            ("第五单元 线和角", u3a_5()), ("第六单元 分数的初步认识", u3a_6()),
            ("第七单元 复习与关联", [u3a_2()[0], u3a_4()[1], u3a_6()[1], u3a_3()[0]])]

# =====================================================================
# 3下
# =====================================================================
def u3b_1():
    items = [("电梯上下运动", "平移"), ("推拉窗户", "平移"), ("风车转动", "旋转"), ("钟表指针走动", "旋转"),
             ("拉抽屉", "平移"), ("旋转木马转动", "旋转"), ("汽车方向盘转动", "旋转"), ("升国旗时国旗的运动", "平移"),
             ("缆车沿直线运动", "平移"), ("电风扇扇叶转动", "旋转")]
    def mv(r):
        q, a = r.choice(items)
        return C(f"“{q}”属于（　）现象。", [a, "旋转" if a == "平移" else "平移", "轴对称", "放大"])
    sym = {"轴对称": ["王", "中", "木", "田", "工", "A", "H", "M", "米", "日"], "非轴对称": ["F", "G", "R", "Z", "N", "S", "J", "P", "L", "Q"]}
    def ax(r):
        right = r.choice(sym["轴对称"]); wr = r.sample(sym["非轴对称"], 3)
        return C("下面哪个字或字母是轴对称图形？", [right] + wr)
    facts = [("长方形有（　）条对称轴。", "2"), ("正方形有（　）条对称轴。", "4"), ("圆有（　）条对称轴。", ["无数", "1", "2", "4"]),
             ("等边三角形有（　）条对称轴。", "3"),
             ("把一张纸对折后剪出的图案，展开后是（　）图形。", ["轴对称", "平移", "旋转", "不规则"])]
    def shift(r):
        a, b = r.randint(1, 5), r.randint(1, 5)
        return C(f"一个小方块先向右平移{a}格，再向左平移{b}格，相当于（　）。", [f"向右平移{a - b}格" if a > b else f"向左平移{b - a}格" if b > a else "回到原处", f"向右平移{a + b}格", f"向左平移{a + b}格", "向上平移1格"])
    return [mv, ax, fact(facts), shift]

def u3b_2():
    def oral(r):
        d = r.randint(2, 9); qt = r.randint(1, 9) * r.choice([10, 100])
        return Fi(f"{d * qt} ÷ {d} = ？", str(qt))
    def exact(r):
        d = r.randint(2, 9); qt = r.randint(12, 199)
        n = d * qt
        if n > 999: return None
        q = f"{n} ÷ {d} = ？"
        if r.random() < .5: return Fi(q, str(qt))
        return C(q, numopts(qt, [qt + 10, qt - 10, qt * 10, qt + 1]))
    def zero(r):
        d = r.randint(2, 9); h, o = r.randint(1, 9), r.randint(1, 9); qt = h * 100 + o
        n = d * qt
        if n > 9999: return None
        return C(f"{n} ÷ {d} = ？（商中间有0）", numopts(qt, [h * 10 + o, qt + 10, qt * 10]))
    def remd(r):
        d = r.randint(3, 9); qt = r.randint(20, 150); rm = r.randint(1, d - 1); n = d * qt + rm
        if n > 999: return None
        return Fi(f"{n} ÷ {d} = （　）……（　）（格式：商……余数）", [f"{qt}……{rm}", f"{qt}...{rm}", f"{qt}…{rm}", f"{qt}余{rm}"])
    def digits(r):
        d = r.randint(2, 9); a = r.randint(1, 9)
        n = a * 100 + r.randint(0, 99)
        w = 3 if a >= d else 2
        return C(f"{n} ÷ {d}的商是（　）位数。", [f"{w}", f"{5 - w}", "1", "4"])
    def word(r):
        d, qt = r.randint(3, 8), r.randint(25, 120)
        return Fi(f"{d}个班一共收集了{d * qt}个废旧电池，平均每班收集多少个？", str(qt))
    return [oral, exact, zero, remd, digits, word]

def u3b_3():
    def rect(r):
        a, b = r.randint(5, 30), r.randint(3, 20)
        if a == b: return None
        p = 2 * (a + b)
        return C(f"一个长方形长{a}厘米，宽{b}厘米，它的周长是（　）厘米。", numopts(p, [a + b, a * b, 2 * a + b]))
    def sq(r):
        a = r.randint(3, 25)
        return Fi(f"一个正方形的边长是{a}分米，它的周长是（　）分米。", str(4 * a))
    def back(r):
        a = r.randint(3, 20)
        return Fi(f"用一根长{4 * a}厘米的铁丝正好围成一个正方形，正方形的边长是（　）厘米。", str(a))
    def back2(r):
        a, b = r.randint(6, 20), r.randint(2, 12)
        if a <= b: return None
        return Fi(f"一个长方形的周长是{2 * (a + b)}米，长是{a}米，宽是（　）米。", str(b))
    def poly(r):
        s = r.choice([("三角形", 3), ("四边形", 4), ("五边形", 5), ("六边形", 6)])
        return Fi(f"{s[0]}有（　）条边。", str(s[1]))
    def two(r):
        a = r.randint(2, 9)
        return C(f"两个边长都是{a}厘米的正方形拼成一个长方形，这个长方形的周长是（　）厘米。", numopts(6 * a, [8 * a, 4 * a, 2 * a * a]))
    return [rect, sq, back, back2, poly, two]

def u3b_4():
    def ra(r):
        a, b = r.randint(3, 20), r.randint(2, 15)
        if a == b: return None
        return C(f"长方形长{a}米，宽{b}米，面积是（　）平方米。", numopts(a * b, [2 * (a + b), a + b, a * b + a]))
    def sa(r):
        a = r.randint(2, 15)
        return C(f"边长是{a}厘米的正方形，面积是（　）平方厘米。", numopts(a * a, [4 * a, 2 * a, a * a + a]))
    def conv(r):
        k = r.randint(2, 9)
        t = r.choice([0, 1, 2, 3])
        if t == 0: return Fi(f"{k}平方米 = （　）平方分米", str(k * 100))
        if t == 1: return Fi(f"{k}平方分米 = （　）平方厘米", str(k * 100))
        if t == 2: return Fi(f"{k * 100}平方厘米 = （　）平方分米", str(k))
        return Fi(f"{k * 100}平方分米 = （　）平方米", str(k))
    def wid(r):
        a, b = r.randint(4, 20), r.randint(2, 12)
        return Fi(f"一块长方形菜地的面积是{a * b}平方米，长{a}米，宽是（　）米。", str(b))
    def tile(r):
        a = r.randint(2, 6)
        return Fi(f"用边长1分米的正方形地砖铺满一块边长{a}米的正方形地面，需要（　）块。", str(a * a * 100))
    def unit(r):
        items = [("一个教室的地面面积约60", "平方米"), ("一张邮票的面积约6", "平方厘米"), ("课桌面的面积约24", "平方分米"),
                 ("数学书封面的面积约4", "平方分米"), ("一块手帕的面积约4", "平方分米"), ("指甲盖的面积约1", "平方厘米")]
        q, a = r.choice(items)
        return C(f"{q}（　）。", [a] + [u for u in ["平方厘米", "平方分米", "平方米", "米"] if u != a])
    return [ra, sa, conv, wid, tile, unit]

def u3b_5():
    def tot(r):
        ns = [r.randint(3, 15) for _ in range(4)]
        return Fi(f"用“正”字记录投票：小红得{ns[0]}票，小明得{ns[1]}票，小刚得{ns[2]}票，小丽得{ns[3]}票。一共有多少张票？", str(sum(ns)))
    def zheng(r):
        k, e = r.randint(1, 5), r.randint(0, 4)
        return Fi(f"用“正”字记录，写了{k}个完整的“正”字和{e}笔，表示（　）。", str(5 * k + e))
    def most(r):
        names = ["晴天", "多云", "阴天", "雨天"]; ns = r.sample(range(2, 15), 4); i = ns.index(max(ns))
        return C("统计某月天气：" + "，".join(f"{a}{b}天" for a, b in zip(names, ns)) + "。哪种天气最多？", [names[i]] + [n for j, n in enumerate(names) if j != i])
    def diff(r):
        a, b = r.randint(10, 30), r.randint(3, 20)
        if a <= b: return None
        return Fi(f"三年级喜欢足球的有{a}人，喜欢排球的有{b}人，喜欢足球的比喜欢排球的多（　）人。", str(a - b))
    return [tot, zheng, most, diff]

def u3b_date():
    def leap(r):
        y = r.choice(list(range(1990, 2040)))
        lp = (y % 4 == 0 and y % 100 != 0) or y % 400 == 0
        return C(f"{y}年是（　）。", ["闰年" if lp else "平年", "平年" if lp else "闰年", "大月", "小月"])
    def feb(r):
        y = r.choice(list(range(2000, 2040)))
        lp = (y % 4 == 0 and y % 100 != 0) or y % 400 == 0
        return Fi(f"{y}年的2月有（　）天。", "29" if lp else "28")
    big = [1, 3, 5, 7, 8, 10, 12]
    def days(r):
        m = r.choice([1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12])
        return Fi(f"{m}月有（　）天。", "31" if m in big else "30")
    def h24(r):
        h = r.randint(1, 11); m = r.choice([0, 10, 20, 30, 45])
        return Fi(f"用24时计时法表示：下午{h}时{f'{m}分' if m else ''}是（　）。（如 15:30）", [f"{h + 12}:{m:02d}", f"{h + 12}时{m}分" if m else f"{h + 12}时"])
    def dur(r):
        a, b = r.randint(7, 11), r.randint(13, 18)
        return Fi(f"商店营业时间是{a}:00～{b}:00，一天营业（　）小时。", str(b - a))
    facts = [("一年有（　）个月。", "12"), ("一年中有（　）个大月。", "7"), ("一年中有（　）个小月（不含2月）。", "4"),
             ("平年全年有（　）天。", "365"), ("闰年全年有（　）天。", "366"),
             ("平年的第一季度有（　）天。", "90"), ("闰年的第一季度有（　）天。", "91")]
    return [leap, feb, days, h24, dur, fact(facts)]

def u3b_6():
    def money(r):
        y, j = r.randint(1, 20), r.randint(1, 9)
        return Fi(f"{y}元{j}角写成用“元”作单位的小数是（　）元。", f"{y}.{j}")
    def dm(r):
        k = r.randint(1, 9)
        return Fi(f"{k}分米 = （　）米（用小数表示）", f"0.{k}")
    def frac(r):
        k = r.randint(1, 9)
        return Fi(f"{k}/10写成小数是（　）。", f"0.{k}")
    def cmp(r):
        a, b = F(r.randint(1, 99), 10), F(r.randint(1, 99), 10)
        if a == b: return None
        return C(f"{dec(a)}和{dec(b)}，哪个大？", [dec(max(a, b)), dec(min(a, b)), "一样大", "无法比较"])
    def add(r):
        a, b = F(r.randint(1, 99), 10), F(r.randint(1, 99), 10)
        if r.random() < .5:
            return Fi(f"{dec(a)} + {dec(b)} = ？", dec(a + b))
        if a < b: a, b = b, a
        if a == b: return None
        return Fi(f"{dec(a)} - {dec(b)} = ？", dec(a - b))
    def word(r):
        a, b = F(r.randint(10, 60), 10), F(r.randint(5, 40), 10)
        return Fi(f"一支笔{dec(a)}元，一本本子{dec(b)}元，一共多少元？", dec(a + b))
    def read(r):
        a = F(r.randint(11, 99), 10)
        i, f = divmod(int(a * 10), 10)
        return C(f"小数{dec(a)}读作（　）。", [f"{cn_int(i)}点{CN[f]}", f"{cn_int(i)}点{CN[f]}零", f"{cn_int(i)}{CN[f]}", f"{cn_int(i)}分之{CN[f]}"])
    return [money, dm, frac, cmp, add, word, read]

def cn_int(n):
    if n < 10: return CN[n]
    t, o = divmod(n, 10)
    return (CN[t] if t > 1 else "") + "十" + (CN[o] if o else "")

def vol_g3b():
    return [("第一单元 生活中的运动现象", u3b_1()), ("第二单元 除数是一位数的除法", u3b_2()),
            ("第三单元 长方形和正方形", u3b_3()), ("第四单元 图形的面积", u3b_4()),
            ("第五单元 数据的收集与整理", u3b_5()), ("综合与实践 年、月、日的秘密", u3b_date()),
            ("第六单元 小数的初步认识", u3b_6()),
            ("第七单元 复习与关联", [u3b_2()[1], u3b_4()[0], u3b_3()[0], u3b_6()[4]])]

# =====================================================================
# 4上
# =====================================================================
POS = ["个", "十", "百", "千", "万", "十万", "百万", "千万", "亿", "十亿"]
def u4a_1():
    def pos(r):
        k = r.randint(4, 9)
        return C(f"从右边起，第{k + 1}位是（　）位。", [POS[k], POS[k - 1], POS[min(k + 1, 9)], POS[k - 2]])
    def wan(r):
        n = r.randint(1, 999) * 10000
        return Fi(f"把{n}改写成用“万”作单位的数是（　）万。", str(n // 10000))
    def approx(r):
        n = r.randint(10000, 9999999)
        a = (n + 5000) // 10000
        if n % 10000 == 5000: return None
        return C(f"把{n}省略万位后面的尾数，约是（　）。", [f"{a}万", f"{n // 10000}万" if n // 10000 != a else f"{a + 1}万", f"{a * 10}万", f"{(n + 500) // 1000}千"])
    def approx_yi(r):
        n = r.randint(100000000, 9999999999)
        a = (n + 50000000) // 100000000
        return Fi(f"把{n}省略亿位后面的尾数，约是（　）亿。", str(a))
    def comp(r):
        a, b, c = r.randint(1, 9), r.randint(1, 9), r.randint(1, 9)
        return Fi(f"由{a}个亿、{b}个万和{c}个一组成的数是（　）。", str(a * 100000000 + b * 10000 + c))
    def cmp(r):
        a, b = r.randint(100000, 9999999), r.randint(100000, 9999999)
        if a == b: return None
        return Fi(f"在○里填“>”或“<”：{a} ○ {b}", ">" if a > b else "<")
    def jl(r):
        k = r.randint(1, 4)
        return C(f"每相邻两个计数单位之间的进率都是（　）。", ["10", "100", "1000", "10000"]) if k == 1 else Fi(f"10个一千万是（　）。", ["1亿", "100000000", "一亿"]) if k == 2 else Fi("1亿里面有（　）个一万。", "10000") if k == 3 else Fi("最小的六位数是（　）。", "100000")
    def zeros(r):
        n = r.choice([30050000, 400600000, 7008000, 50000600, 2030400])
        s = str(n)
        return Fi(f"{n}这个数中一共有（　）个0。", str(s.count("0")))
    return [pos, wan, approx, approx_yi, comp, cmp, jl, zeros]

def u4a_2():
    def kind(r):
        a = r.randint(1, 359)
        k = "锐角" if a < 90 else "直角" if a == 90 else "钝角" if a < 180 else "平角" if a == 180 else "周角" if a == 360 else None
        if k is None: return None
        return C(f"{a}°的角是（　）。", [k] + [x for x in ["锐角", "直角", "钝角", "平角"] if x != k][:3])
    def comp(r):
        a = r.randint(10, 80)
        return Fi(f"已知∠1 + ∠2 = 90°，∠1 = {a}°，∠2 = （　）°。", str(90 - a))
    def supp(r):
        a = r.randint(15, 165)
        return Fi(f"一个平角被分成两个角，其中一个是{a}°，另一个是（　）°。", str(180 - a))
    def clock(r):
        h = r.randint(1, 6)
        ang = 30 * h
        return C(f"钟面上{h}时整，时针和分针所夹的较小角是（　）°。", numopts(ang, [ang + 30, ang - 15 if ang > 15 else ang + 60, 6 * h]))
    facts = [("1个平角 = （　）个直角。", "2"), ("1个周角 = （　）个直角。", "4"), ("1个周角 = （　）°。", "360"),
             ("用量角器量角时，量角器的中心要和角的（　）重合。", ["顶点", "一条边", "0刻度线", "外圈刻度"]),
             ("把一个角放在放大5倍的放大镜下看，这个角的度数（　）。", ["不变", "扩大5倍", "缩小5倍", "扩大10倍"])]
    def tri(r):
        return C("用一副三角尺不能直接拼出的角是（　）。", [r.choice(["100°", "50°", "80°"]), "75°", "135°", "120°"])
    return [kind, comp, supp, clock, fact(facts), tri]

def u4a_3():
    def m22(r):
        a, b = r.randint(11, 99), r.randint(11, 99)
        p = a * b; q = f"{a} × {b} = ？"
        if r.random() < .5: return Fi(q, str(p))
        return C(q, numopts(p, [a * (b % 10) + a * (b // 10), p + 10, p - a, p + b]))
    def m32(r):
        a, b = r.randint(101, 999), r.randint(11, 99)
        return Fi(f"{a} × {b} = ？", str(a * b))
    def oral(r):
        a, b = r.randint(2, 9) * 10, r.randint(2, 9) * 10
        return Fi(f"{a} × {b} = ？", str(a * b))
    def law(r):
        a, b, k = r.randint(12, 60), r.randint(3, 20), r.choice([2, 3, 5, 10])
        return Fi(f"已知 {a} × {b} = {a * b}，那么 {a * k} × {b} = （　）。", str(a * k * b))
    def word(r):
        v, t = r.randint(45, 95), r.randint(12, 30)
        return Fi(f"一列火车每小时行驶{v}千米，{t}小时行驶多少千米？", str(v * t))
    def price(r):
        p, n = r.randint(15, 98), r.randint(12, 45)
        return Fi(f"每套校服{p}元，学校订购了{n}套，一共需要多少元？", str(p * n))
    def zeros(r):
        a, b = r.randint(1, 9) * 100 + r.randint(1, 9) * 10, r.randint(1, 9) * 10
        p = a * b
        return C(f"{a} × {b}的积的末尾有（　）个0。", numopts(len(str(p)) - len(str(p).rstrip('0')), [2, 1, 3, 4]))
    return [m22, m32, oral, law, word, price, zeros]

def u4a_4():
    def total(r):
        a, b = r.randint(120, 600), r.randint(80, 500)
        return Fi(f"一本书上午看了{a}字，下午看了{b}字，一共看了多少字？（总量 = 部分量 + 部分量）", str(a + b))
    def part(r):
        s, a = r.randint(500, 999), r.randint(100, 400)
        return Fi(f"学校共有学生{s}人，其中男生{a}人，女生有多少人？", str(s - a))
    def up(r):
        p, n = r.randint(12, 60), r.randint(3, 15)
        return C(f"单价{p}元，数量{n}个，总价是多少元？", numopts(p * n, [p + n, p * n + p, p * (n - 1)]))
    def price(r):
        p, n = r.randint(12, 60), r.randint(3, 15)
        return Fi(f"买{n}个同样的书包共{p * n}元，每个书包多少元？（单价 = 总价 ÷ 数量）", str(p))
    def road(r):
        v, t = r.randint(40, 90), r.randint(2, 8)
        return Fi(f"一辆汽车{t}小时行驶了{v * t}千米，它的速度是每小时多少千米？", str(v))
    def time(r):
        v, t = r.randint(50, 120), r.randint(2, 9)
        return Fi(f"甲、乙两地相距{v * t}千米，一辆车每小时行{v}千米，几小时能到达？", str(t))
    def which(r):
        return C(r.choice(["速度、时间、路程三者的关系是（　）。"]), ["路程 = 速度 × 时间", "路程 = 速度 + 时间", "速度 = 路程 × 时间", "时间 = 速度 × 路程"])
    return [total, part, up, price, road, time, which]

def u4a_5():
    facts = [("在同一平面内，不相交的两条直线叫作（　）。", ["平行线", "垂线", "射线", "线段"]),
             ("两条直线相交成直角时，这两条直线（　）。", ["互相垂直", "互相平行", "重合", "不相交"]),
             ("从直线外一点到这条直线所画的线段中，（　）最短。", ["垂直线段", "斜线段", "平行线段", "任意线段"]),
             ("两组对边分别平行的四边形叫作（　）。", ["平行四边形", "梯形", "三角形", "五边形"]),
             ("只有一组对边平行的四边形叫作（　）。", ["梯形", "平行四边形", "长方形", "正方形"]),
             ("两腰相等的梯形叫作（　）。", ["等腰梯形", "直角梯形", "平行四边形", "长方形"]),
             ("平行四边形（　）。", ["容易变形", "具有稳定性", "四条边一定都相等", "四个角一定都是直角"]),
             ("长方形和正方形都是特殊的（　）。", ["平行四边形", "梯形", "三角形", "五边形"]),
             ("在同一平面内，过直线外一点可以画（　）条已知直线的平行线。", ["1", "2", "无数", "0"]),
             ("梯形有（　）条高。", ["无数", "1", "2", "4"])]
    def per(r):
        a, b = r.randint(5, 30), r.randint(3, 25)
        return Fi(f"一个平行四边形相邻两条边分别长{a}厘米和{b}厘米，它的周长是（　）厘米。", str(2 * (a + b)))
    def trap(r):
        a, b, c = r.randint(4, 15), r.randint(8, 25), r.randint(3, 10)
        if a >= b: return None
        return Fi(f"一个等腰梯形，上底{a}厘米，下底{b}厘米，腰长{c}厘米，周长是（　）厘米。", str(a + b + 2 * c))
    def ang(r):
        a = r.randint(40, 80)
        return Fi(f"平行四边形的一个角是{a}°，与它相邻的角是（　）°。", str(180 - a))
    return [fact(facts), per, trap, ang]

def u4a_6():
    def read(r):
        k, n = r.choice([2, 5, 10, 20]), r.randint(3, 12)
        return Fi(f"条形统计图中，1格代表{k}人，某一直条有{n}格，表示（　）人。", str(k * n))
    def diff(r):
        a, b = r.randint(10, 60), r.randint(10, 60)
        if a == b: return None
        return Fi(f"条形统计图显示：四(1)班借书{a}本，四(2)班借书{b}本，两班相差（　）本。", str(abs(a - b)))
    def tot(r):
        ns = [r.randint(10, 50) for _ in range(4)]
        return Fi("条形统计图显示一周四天卖出的面包分别是" + "、".join(map(str, ns)) + "个，这四天一共卖出（　）个。", str(sum(ns)))
    def scale(r):
        mx = r.randint(30, 200)
        k = 2 if mx <= 40 else 5 if mx <= 100 else 10 if mx <= 200 else 20
        opts = [str(k), "1", str(k * 10), "100" if k != 100 else "50"]
        if len(set(opts)) < 4: return None
        return C(f"要画条形统计图，数据最大是{mx}，最小也超过10，大约用20格以内画出，1格表示几比较合适？", opts)
    def yi(r):
        return Fi("1亿有多大：1亿 = （　）个一万。", "10000") if r.random() < .5 else Fi("一张纸厚约0.1毫米，1万张纸叠起来大约厚（　）毫米。", "1000")
    return [read, diff, tot, yi]

def vol_g4a():
    return [("第一单元 万以上数的认识", u4a_1()), ("第二单元 角的度量", u4a_2()),
            ("第三单元 多位数乘两位数", u4a_3()), ("第四单元 加法模型和乘法模型", u4a_4()),
            ("第五单元 平行四边形和梯形", u4a_5()), ("第六单元 条形统计图", u4a_6()),
            ("第七单元 复习与关联", [u4a_3()[0], u4a_1()[2], u4a_2()[2], u4a_4()[4]])]

# =====================================================================
# 4下 (provisional)
# =====================================================================
def u4b_1():
    def order(r):
        a, b, c, d = r.randint(100, 500), r.randint(2, 9), r.randint(10, 40), r.randint(2, 9)
        v = a - b * c
        if v < 0: return None
        return C(f"{a} - {b} × {c} = ？", numopts(v, [(a - b) * c, v + 10, a - b + c * 0 - c, v - 10]))
    def paren(r):
        d = r.randint(2, 9); s = d * r.randint(10, 50); a = r.randint(1, s - 1)
        return Fi(f"({a} + {s - a}) ÷ {d} = ？", str(s // d))
    def bracket(r):
        a, b, c, d = r.randint(2, 9), r.randint(20, 60), r.randint(2, 9), r.randint(3, 9)
        inner = b - c * d
        if inner <= 0: return None
        return Fi(f"{a} × [{b} - {c} × {d}] = ？", str(a * inner))
    def rel(r):
        a, b = r.randint(100, 900), r.randint(100, 900)
        return C(f"已知 {a} + {b} = {a + b}，那么 {a + b} - {b} = （　）。", numopts(a, [b, a + b, a - b if a > b else a + 1]))
    def zero(r):
        return C(r.choice(["0除以任何不是0的数都得（　）。", "任何数乘0都得（　）。"]), ["0", "1", "原数", "无法确定"])
    def div2(r):
        d, qt = r.randint(12, 49), r.randint(3, 30)
        return Fi(f"{d * qt} ÷ {d} = ？", str(qt))
    return [order, paren, bracket, rel, zero, div2]

def u4b_2():
    facts = [("从不同位置观察同一个物体，看到的形状（　）。", ["可能不同", "一定相同", "一定不同", "都是长方形"]),
             ("一个物体从正面看是正方形，它（　）是正方体。", ["不一定", "一定", "一定不", "必须"]),
             ("从同一位置观察不同的物体，看到的形状（　）。", ["可能相同", "一定不同", "一定相同", "都是圆"])]
    def row(r):
        n = r.randint(2, 6)
        return Fi(f"{n}个小正方体摆成一排，从上面看到（　）个正方形。", str(n))
    def L(r):
        a, b = r.randint(2, 5), r.randint(1, 3)
        return Fi(f"底层一排摆{a}个小正方体，在最左边那个上面再叠{b}个，从正面看共看到（　）个正方形。", str(a + b))
    return [fact(facts), row, L]

def u4b_3():
    def comm(r):
        a, b, c = r.randint(20, 90), r.randint(10, 90), None
        c = 100 - b if b < 100 else None
        if not c or c <= 0: return None
        return Fi(f"简便计算：{b} + {a} + {c} = ？", str(a + b + c))
    def assoc(r):
        a = r.choice([25, 125]); b = 4 if a == 25 else 8; c = r.randint(3, 40)
        return Fi(f"简便计算：{a} × {c} × {b} = ？", str(a * b * c))
    def dist(r):
        a, b, c = r.randint(11, 99), r.randint(10, 60), None
        c = 100 - b
        return Fi(f"简便计算：{a} × {b} + {a} × {c} = ？", str(a * 100))
    def near(r):
        a = r.randint(12, 60); b = r.choice([99, 101, 98, 102])
        return Fi(f"简便计算：{a} × {b} = ？", str(a * b))
    def name(r):
        k = r.randint(0, 3)
        laws = [("a + b = b + a", "加法交换律"), ("(a + b) + c = a + (b + c)", "加法结合律"),
                ("a × b = b × a", "乘法交换律"), ("(a + b) × c = a × c + b × c", "乘法分配律")]
        q, a = laws[k]
        return C(f"“{q}”表示的是（　）。", [a] + [x for _, x in laws if x != a])
    def sub(r):
        a, b, c = r.randint(300, 900), r.randint(20, 80), None
        c = 100 - b
        return Fi(f"简便计算：{a} - {b} - {c} = ？", str(a - 100))
    return [comm, assoc, dist, near, name, sub]

def u4b_4():
    def mv(r):
        x = F(r.randint(1, 9999), 100); k = r.choice([10, 100, 1000])
        if r.random() < .5: return Fi(f"{dec(x)} × {k} = ？", dec(x * k))
        return Fi(f"{dec(x)} ÷ {k} = ？", dec(x / k))
    def cmp(r):
        a, b = F(r.randint(100, 999), 100), F(r.randint(100, 999), 1000)
        if a == b: return None
        return C(f"{dec(a)}和{dec(b)}，哪个大？", [dec(max(a, b)), dec(min(a, b)), "一样大", "无法比较"])
    def prop(r):
        x = F(r.randint(1, 99), 10)
        return C(f"根据小数的性质，与{dec(x)}相等的数是（　）。", [dec(x) + "0", dec(x * 10), dec(x / 10), dec(x) + "1"])
    def unit(r):
        k = r.randint(1, 999)
        t = r.choice([0, 1, 2])
        if t == 0: return Fi(f"{k}厘米 = （　）米", dec(F(k, 100)))
        if t == 1: return Fi(f"{k}克 = （　）千克", dec(F(k, 1000)))
        return Fi(f"{k}米 = （　）千米", dec(F(k, 1000)))
    def appr(r):
        x = F(r.randint(1000, 99999), 1000)
        a = F(int(x * 100 + F(1, 2)), 100)
        return Fi(f"把{dec(x)}保留两位小数（四舍五入）约是（　）。", [f"{float(a):.2f}", dec(a)])
    def place(r):
        x = F(r.randint(1000, 9999), 1000)
        s = dec(x).ljust(5, "0")
        return Fi(f"{s}的百分位上的数是（　）。", s[3])
    def meaning(r):
        k = r.randint(1, 99)
        return Fi(f"{k}/100写成小数是（　）。", dec(F(k, 100)))
    return [mv, cmp, prop, unit, appr, place, meaning]

def u4b_5():
    def third(r):
        a, b = r.randint(20, 100), r.randint(20, 100)
        if a + b >= 180: return None
        return Fi(f"三角形的两个内角分别是{a}°和{b}°，第三个角是（　）°。", str(180 - a - b))
    def kind(r):
        a, b = r.randint(20, 100), r.randint(20, 100)
        c = 180 - a - b
        if c <= 0: return None
        m = max(a, b, c)
        k = "锐角三角形" if m < 90 else "直角三角形" if m == 90 else "钝角三角形"
        return C(f"一个三角形的三个角分别是{a}°、{b}°、{c}°，它是（　）。", [k] + [x for x in ["锐角三角形", "直角三角形", "钝角三角形", "等边三角形"] if x != k])
    def side(r):
        a, b = r.randint(3, 12), r.randint(3, 12)
        lo, hi = abs(a - b), a + b
        right = r.randint(lo + 1, hi - 1); wrong = [hi, hi + r.randint(1, 5), max(lo, 1) if lo >= 1 else hi + 6]
        opts = [str(right)] + [str(w) for w in wrong]
        if len(set(opts)) < 4: return None
        return C(f"三角形两条边长{a}厘米和{b}厘米，第三条边可能是（　）厘米。", opts)
    facts = [("三角形的内角和是（　）°。", "180"), ("三角形具有（　）。", ["稳定性", "易变形性", "四条边", "两条高"]),
             ("等边三角形的每个内角都是（　）°。", "60"),
             ("一个三角形中最多有（　）个直角。", "1"), ("一个三角形中最多有（　）个钝角。", "1"),
             ("四边形的内角和是（　）°。", "360")]
    def iso(r):
        top = r.randrange(20, 160, 2)
        return Fi(f"等腰三角形的顶角是{top}°，一个底角是（　）°。", str((180 - top) // 2))
    return [third, kind, side, fact(facts), iso]

def u4b_6():
    def add(r):
        a, b = F(r.randint(1, 9999), 100), F(r.randint(1, 9999), 100)
        q = f"{dec(a)} + {dec(b)} = ？"
        return Fi(q, dec(a + b))
    def sub(r):
        a, b = F(r.randint(100, 9999), 100), F(r.randint(1, 999), 100)
        if a <= b: return None
        return Fi(f"{dec(a)} - {dec(b)} = ？", dec(a - b))
    def sub2(r):
        a, b = r.randint(5, 20), F(r.randint(101, 499), 100)
        return C(f"{a} - {dec(b)} = ？", numopts(a - b, [a - b + 1, a - b - F(1, 10), a - b + F(1, 10)]))
    def easy(r):
        a, b, c = F(r.randint(10, 99), 10), F(r.randint(1, 99), 100), None
        c = 10 - a if a < 10 else None
        if c is None or c <= 0: return None
        return Fi(f"简便计算：{dec(a)} + {dec(b)} + {dec(c)} = ？", dec(a + b + c))
    def word(r):
        a, b = F(r.randint(150, 900), 100), F(r.randint(50, 500), 100)
        return Fi(f"妈妈买菜用了{dec(a)}元，买水果用了{dec(b)}元，一共用了多少元？", dec(a + b))
    return [add, sub, sub2, easy, word]

def u4b_7():
    facts = [("长方形有（　）条对称轴。", "2"), ("正方形有（　）条对称轴。", "4"), ("等腰梯形有（　）条对称轴。", "1"),
             ("平行四边形（一般的）有（　）条对称轴。", "0"), ("圆有（　）条对称轴。", ["无数", "1", "2", "4"]),
             ("轴对称图形中，对称点到对称轴的距离（　）。", ["相等", "不相等", "成2倍", "无法确定"]),
             ("图形平移后，（　）不变。", ["形状和大小", "位置", "方向和位置", "只有颜色"])]
    def mv(r):
        a, b = r.randint(1, 8), r.randint(1, 8)
        x, y = r.randint(1, 5), r.randint(1, 5)
        return Fi(f"在方格纸上，点A在第{x}列第{y}行，先向右平移{a}格，再向上平移{b}格，它到了第（　）列第（　）行。（用逗号隔开）", [f"{x + a},{y + b}", f"{x + a}，{y + b}", f"{x + a}、{y + b}"])
    def dist(r):
        d = r.randint(2, 9)
        return Fi(f"点A到对称轴的距离是{d}格，它的对称点A′到对称轴的距离是（　）格。", str(d))
    return [fact(facts), mv, dist]

def u4b_8():
    def avg(r):
        n = r.randint(3, 5); avgv = r.randint(10, 90)
        vals = [avgv + r.randint(-8, 8) for _ in range(n - 1)]
        last = avgv * n - sum(vals)
        if last <= 0: return None
        vals.append(last)
        return Fi("求平均数：" + "、".join(map(str, vals)) + "的平均数是（　）。", str(avgv))
    def word(r):
        n = r.randint(3, 6); avgv = r.randint(80, 98)
        return Fi(f"小明{n}次数学测验的平均分是{avgv}分，他{n}次一共得了（　）分。", str(avgv * n))
    def miss(r):
        a, b, avgv = r.randint(80, 99), r.randint(80, 99), r.randint(85, 95)
        c = avgv * 3 - a - b
        if not (0 < c <= 100): return None
        return Fi(f"小红语文{a}分，英语{b}分，三科平均分是{avgv}分，数学得了（　）分。", str(c))
    def fact1(r):
        return C("平均数（　）。", ["在最大数和最小数之间", "一定比最大数大", "一定等于其中某个数", "一定比最小数小"])
    def bar(r):
        a, b = r.randint(10, 40), r.randint(10, 40)
        if a == b: return None
        return Fi(f"复式条形统计图中，四(1)班男生{a}人、女生{b}人，全班共（　）人。", str(a + b))
    return [avg, word, miss, fact1, bar]

def u4b_9():
    def jt(r):
        c, rb = r.randint(2, 15), r.randint(2, 15)
        h, f = c + rb, 2 * c + 4 * rb
        k = r.choice(["鸡", "兔"])
        ans = c if k == "鸡" else rb
        return C(f"笼子里有鸡和兔共{h}只，脚共{f}只，{k}有（　）只。", numopts(ans, [rb if k == "鸡" else c, h - ans + 1, ans + 2]))
    def boat(r):
        b, s = r.randint(2, 8), r.randint(2, 8)
        n, p = b + s, 6 * b + 4 * s
        return Fi(f"大船每条坐6人，小船每条坐4人，共租了{n}条船，正好坐{p}人，租了大船（　）条。", str(b))
    def ass(r):
        c, rb = r.randint(3, 12), r.randint(3, 12)
        h, f = c + rb, 2 * c + 4 * rb
        return Fi(f"鸡兔同笼，共{h}个头、{f}只脚。假设全是鸡，就少了（　）只脚。", str(f - 2 * h))
    return [jt, boat, ass]

def vol_g4b():
    return [("第一单元 四则运算", u4b_1()), ("第二单元 观察物体（二）", u4b_2()), ("第三单元 运算定律", u4b_3()),
            ("第四单元 小数的意义和性质", u4b_4()), ("第五单元 三角形", u4b_5()), ("第六单元 小数的加法和减法", u4b_6()),
            ("第七单元 图形的运动（二）", u4b_7()), ("第八单元 平均数与条形统计图", u4b_8()),
            ("第九单元 数学广角——鸡兔同笼", u4b_9())]

# =====================================================================
# 5上
# =====================================================================
def u5a_1():
    facts = [("从不同方向观察一个组合体，看到的形状（　）。", ["可能不同", "一定相同", "一定不同", "都是正方形"]),
             ("一个由小正方体搭成的组合体，从正面看到的图形只能确定（　）。", ["正面的形状", "小正方体的总数", "从上面看到的形状", "从左面看到的形状"])]
    def cnt(r):
        a, b = r.randint(2, 4), r.randint(2, 3)
        return Fi(f"用小正方体搭成一个{a}个长、{b}个宽、1层高的长方体，一共用了（　）个小正方体。", str(a * b))
    def cnt2(r):
        a, b, c = r.randint(2, 4), r.randint(2, 3), r.randint(2, 3)
        return Fi(f"用小正方体搭成长{a}个、宽{b}个、高{c}层的长方体，一共用了（　）个小正方体。", str(a * b * c))
    def front(r):
        a, c = r.randint(2, 5), r.randint(1, 3)
        return Fi(f"一个组合体：底层一排{a}个小正方体，最右边那个上面再叠{c}个。从正面看能看到（　）个正方形。", str(a + c))
    return [fact(facts), cnt, cnt2, front]

def u5a_2():
    def di(r):
        a = F(r.randint(11, 999), 10); b = r.randint(2, 30)
        return Fi(f"{dec(a)} × {b} = ？", dec(a * b))
    def dd(r):
        a, b = F(r.randint(11, 99), 10), F(r.randint(11, 99), 10)
        p = a * b; q = f"{dec(a)} × {dec(b)} = ？"
        if r.random() < .5: return Fi(q, dec(p))
        return C(q, numopts(p, [p * 10, p / 10, p + 1]))
    def places(r):
        a, b = F(r.randint(11, 999), 100), F(r.randint(11, 99), 10)
        return C(f"{dec(a)} × {dec(b)}的积有几位小数？（先不计算末尾的0）", ["3位" if True else "", "2位", "1位", "4位"])
    def cmpk(r):
        a = F(r.randint(11, 99), 10); b = F(r.randint(1, 9), 10)
        return C(f"不计算，比较大小：{dec(a)} × {dec(b)} ○ {dec(a)}", ["<", ">", "=", "无法比较"])
    def appr(r):
        a, b = F(r.randint(101, 999), 100), F(r.randint(11, 99), 10)
        p = a * b
        ap = F(int(p * 10 + F(1, 2)), 10)
        s = f"{float(ap):.1f}"
        return Fi(f"{dec(a)} × {dec(b)}的积保留一位小数约是（　）。", [s, dec(ap)])
    def word(r):
        p, n = F(r.randint(25, 120), 10), r.randint(3, 12)
        return Fi(f"苹果每千克{dec(p)}元，买{n}千克要多少元？", dec(p * n))
    def law(r):
        a = F(r.randint(11, 99), 10)
        return Fi(f"简便计算：{dec(a)} × 0.25 × 4 = ？", dec(a))
    return [di, dd, places, cmpk, appr, word, law]

def u5a_3():
    def dint(r):
        d = r.randint(2, 12); qt = F(r.randint(11, 999), 100)
        return Fi(f"{dec(qt * d)} ÷ {d} = ？", dec(qt))
    def ddec(r):
        d = F(r.randint(2, 99), 10); qt = F(r.randint(2, 99), 10)
        n = d * qt
        q = f"{dec(n)} ÷ {dec(d)} = ？"
        if r.random() < .5: return Fi(q, dec(qt))
        return C(q, numopts(qt, [qt * 10, qt / 10, qt + 1]))
    def rep(r):
        a, b = r.choice([(1, 3), (2, 3), (1, 6), (5, 6), (1, 9), (4, 9), (7, 9), (2, 9)])
        # repeating decimal
        s = dec(F(int(F(a, b) * 1000), 1000))
        return C(f"{a} ÷ {b}的商是（　）。", ["循环小数", "有限小数", "整数", "分数以外的数都不是"])
    def appr(r):
        a, b = r.randint(10, 99), r.choice([3, 6, 7, 9, 11])
        v = F(a, b); ap = F(int(v * 100 + F(1, 2)), 100)
        s = f"{float(ap):.2f}"
        return Fi(f"{a} ÷ {b}的商保留两位小数约是（　）。", [s, dec(ap)])
    def cmpk(r):
        a = F(r.randint(11, 99), 10); b = F(r.randint(1, 9), 10)
        return C(f"不计算，比较大小：{dec(a)} ÷ {dec(b)} ○ {dec(a)}", [">", "<", "=", "无法比较"])
    def bottles(r):
        cap = F(r.choice([25, 15, 4, 8]), 10); total = r.randint(5, 30)
        n = total / cap
        k = int(n) + (0 if n == int(n) else 1)
        if n == int(n): return None
        return C(f"有{total}千克油，每个瓶子最多装{dec(cap)}千克，至少需要几个瓶子？", numopts(k, [int(n), k + 1, total]))
    def most(r):
        p = F(r.choice([35, 45, 65, 85, 25]), 10); m = r.randint(10, 50)
        k = int(m / p)
        if m / p == k: return None
        return C(f"妈妈有{m}元，每支笔{dec(p)}元，最多能买几支？", numopts(k, [k + 1, k - 1, m]))
    return [dint, ddec, rep, appr, cmpk, bottles, most]

def u5a_4():
    facts = [("下面图形中，对称轴最多的是（　）。", ["圆", "正方形", "长方形", "等边三角形"]),
             ("钟表的指针转动属于（　）。", ["旋转", "平移", "轴对称", "放大"]),
             ("把一个图形绕某点顺时针旋转90°后，图形的大小（　）。", ["不变", "变大", "变小", "无法确定"]),
             ("推拉门的运动属于（　）。", ["平移", "旋转", "轴对称", "缩小"]),
             ("时针从12走到3，绕中心顺时针旋转了（　）°。", "90"), ("分针走一圈，旋转了（　）°。", "360"),
             ("正方形有（　）条对称轴。", "4"), ("正六边形有（　）条对称轴。", "6"),
             ("等腰三角形（不等边）有（　）条对称轴。", "1")]
    def clock(r):
        a = r.randint(1, 11); b = r.randint(1, 11)
        if a == b: return None
        d = (b - a) % 12 * 30
        return Fi(f"时针从“{a}”顺时针旋转到“{b}”，旋转了（　）°。", str(d))
    def mins(r):
        m = r.randint(1, 11) * 5
        return Fi(f"分针走了{m}分钟，绕中心顺时针旋转了（　）°。", str(m * 6))
    return [fact(facts), clock, mins]

def u5a_5():
    def ev(r):
        a, x = r.randint(2, 9), r.randint(2, 20)
        b = r.randint(1, 30)
        return Fi(f"当x = {x}时，{a}x + {b}的值是（　）。", str(a * x + b))
    def eq1(r):
        x, a = r.randint(2, 50), r.randint(2, 50)
        return Fi(f"解方程：x + {a} = {x + a}，x = （　）", str(x))
    def eq2(r):
        x, a = r.randint(2, 30), r.randint(2, 9)
        return Fi(f"解方程：{a}x = {a * x}，x = （　）", str(x))
    def eq3(r):
        x, a, b = r.randint(2, 20), r.randint(2, 9), r.randint(1, 30)
        return Fi(f"解方程：{a}x - {b} = {a * x - b}，x = （　）", str(x)) if a * x - b > 0 else None
    def eq4(r):
        x = F(r.randint(11, 99), 10); a = F(r.randint(11, 59), 10)
        return Fi(f"解方程：x - {dec(a)} = {dec(x - a)}，x = （　）", dec(x)) if x > a else None
    def expr(r):
        a = r.randint(2, 9)
        return C(f"小明今年a岁，爸爸比小明大{a * 5}岁，爸爸今年（　）岁。", [f"a + {a * 5}", f"a - {a * 5}", f"{a * 5}a", f"a ÷ {a * 5}"])
    def which(r):
        return C("下面是方程的是（　）。", [r.choice(["3x + 5 = 20", "x - 4 = 8", "2x = 18"]), "3x + 5", "3 + 5 = 8", "x + 2 > 7"])
    def simp(r):
        a, b = r.randint(2, 9), r.randint(2, 9)
        return C(f"化简：{a}x + {b}x = （　）", [f"{a + b}x", f"{a * b}x", f"{a + b}x²", f"{a}x{b}"])
    def word(r):
        x, a = r.randint(5, 30), r.randint(2, 6)
        return Fi(f"一个数的{a}倍是{a * x}，这个数是多少？（可列方程{a}x = {a * x}）", str(x))
    return [ev, eq1, eq2, eq3, eq4, expr, which, simp, word]

def u5a_6():
    def para(r):
        a, h = r.randint(3, 25), r.randint(2, 20)
        return C(f"平行四边形底{a}厘米，高{h}厘米，面积是（　）平方厘米。", numopts(a * h, [a * h / F(2), 2 * (a + h), a + h]))
    def tri(r):
        a, h = r.randint(3, 25), r.randint(2, 20)
        s = F(a * h, 2)
        return C(f"三角形底{a}米，高{h}米，面积是（　）平方米。", numopts(s, [a * h, s + a, a + h]))
    def trap(r):
        a, b, h = r.randint(2, 15), r.randint(5, 25), r.randint(2, 12)
        if a >= b: return None
        s = F((a + b) * h, 2)
        return C(f"梯形上底{a}分米，下底{b}分米，高{h}分米，面积是（　）平方分米。", numopts(s, [(a + b) * h, a * b * h / F(2), s + h]))
    def back(r):
        a, h = r.randint(3, 20), r.randint(2, 15)
        return Fi(f"一个三角形面积是{dec(F(a * h, 2))}平方厘米，底是{a}厘米，高是（　）厘米。", str(h))
    def back2(r):
        a, h = r.randint(3, 20), r.randint(2, 15)
        return Fi(f"一个平行四边形面积是{a * h}平方米，高是{h}米，底是（　）米。", str(a))
    def same(r):
        return C("等底等高的三角形面积是平行四边形面积的（　）。", ["一半", "2倍", "相等", "4倍"])
    def ha(r):
        k = r.randint(1, 9)
        return Fi(f"{k}公顷 = （　）平方米", str(k * 10000)) if r.random() < .5 else Fi(f"{k}平方千米 = （　）公顷", str(k * 100))
    return [para, tri, trap, back, back2, same, ha]

def u5a_7():
    def big(r):
        a, b = r.sample(range(1, 12), 2)
        c1, c2 = r.sample(["红", "黄", "蓝", "白", "绿"], 2)
        bigc = c1 if a > b else c2
        return C(f"盒子里有{a}个{c1}球和{b}个{c2}球（大小相同），任意摸一个，摸到哪种颜色的球可能性大？", [bigc + "球", (c2 if bigc == c1 else c1) + "球", "一样大", "一定摸到" + bigc + "球"])
    def cert(r):
        c = r.choice(["红", "黄", "蓝"]); n = r.randint(3, 9)
        k = r.choice([0, 1, 2])
        if k == 0: return C(f"袋子里只有{n}个{c}球，任意摸一个，（　）是{c}球。", ["一定", "可能", "不可能", "很少"])
        if k == 1: return C(f"袋子里只有{n}个{c}球，任意摸一个，（　）是白球。", ["不可能", "一定", "可能", "经常"])
        return C(f"袋子里有{n}个{c}球和1个白球，任意摸一个，（　）是白球。", ["可能", "一定", "不可能", "必然"])
    def dice(r):
        return C(r.choice(["掷一枚骰子，掷出的点数（　）是7。", "明天太阳（　）从西边升起。"]), ["不可能", "可能", "一定", "经常"])
    def fair(r):
        a = r.randint(2, 6); b = r.randint(2, 6)
        ok = "公平" if a == b else "不公平"
        return C(f"盒子里有{a}个红球、{b}个黄球，摸到红球甲赢，摸到黄球乙赢，这个游戏（　）。", [ok, "不公平" if ok == "公平" else "公平", "无法判断", "一定甲赢"])
    return [big, cert, dice, fair]

def vol_g5a():
    return [("第一单元 观察简单组合体", u5a_1()), ("第二单元 小数乘法", u5a_2()), ("第三单元 小数除法", u5a_3()),
            ("第四单元 图形的运动", u5a_4()), ("第五单元 用字母表示数和数量关系", u5a_5()),
            ("第六单元 多边形的面积", u5a_6()), ("第七单元 可能性", u5a_7()),
            ("第八单元 复习与关联", [u5a_2()[1], u5a_3()[1], u5a_5()[2], u5a_6()[2]])]

# =====================================================================
# 5下 (provisional)
# =====================================================================
def is_prime(n): return n > 1 and all(n % p for p in range(2, int(n ** .5) + 1))
def u5b_1():
    facts = [("从正面、左面、上面看到的图形都相同的立体图形是（　）。", ["正方体", "长方体", "圆柱", "三棱柱"]),
             ("只根据从一个方向看到的图形，（　）确定立体图形的形状。", ["不能", "一定能", "总能", "只能"])]
    def cnt(r):
        a, b = r.randint(2, 4), r.randint(2, 4)
        return Fi(f"从上面看是{a}×{b}的长方形（共{a * b}个正方形），从正面看每列都只有1层，这个组合体由（　）个小正方体组成。", str(a * b))
    return [fact(facts), cnt]

def u5b_2():
    def factors(r):
        n = r.choice([12, 18, 20, 24, 30, 36, 16, 28, 40, 45, 48])
        fs_ = [d for d in range(1, n + 1) if n % d == 0]
        return Fi(f"{n}一共有（　）个因数。", str(len(fs_)))
    def prime(r):
        ps = [p for p in range(11, 60) if is_prime(p)]; cs = [c for c in range(10, 60) if not is_prime(c)]
        return C("下面的数中，是质数的是（　）。", [str(r.choice(ps))] + [str(x) for x in r.sample(cs, 3)])
    def m3(r):
        n = r.randint(100, 999)
        return C(f"{n}（　）3的倍数。", ["是" if n % 3 == 0 else "不是", "不是" if n % 3 == 0 else "是", "无法判断", "既是又不是"])
    def m25(r):
        cands = [n for n in range(10, 200) if n % 10 == 0]; non = [n for n in range(10, 200) if n % 10]
        return C("下面的数中，同时是2和5的倍数的是（　）。", [str(r.choice(cands))] + [str(x) for x in r.sample([n for n in non if n % 5 == 0 or n % 2 == 0], 3)])
    def gcd_(r):
        a, b = r.randint(6, 48), r.randint(6, 48)
        return Fi(f"{a}和{b}的最大公因数是（　）。", str(gcd(a, b)))
    def lcm_(r):
        a, b = r.randint(2, 15), r.randint(2, 15)
        return Fi(f"{a}和{b}的最小公倍数是（　）。", str(a * b // gcd(a, b)))
    def odd(r):
        a, b = r.randint(1, 99), r.randint(1, 99)
        s = a + b
        return C(f"{a} + {b}的和是（　）。", ["偶数" if s % 2 == 0 else "奇数", "奇数" if s % 2 == 0 else "偶数", "质数", "无法判断"])
    facts = [("最小的质数是（　）。", "2"), ("最小的合数是（　）。", "4"), ("1既不是质数，也不是（　）。", ["合数", "奇数", "因数", "自然数"]),
             ("一个数的最小倍数是（　）。", ["它本身", "1", "0", "2"])]
    return [factors, prime, m3, m25, gcd_, lcm_, odd, fact(facts)]

def u5b_3():
    def vol(r):
        a, b, c = r.randint(2, 15), r.randint(2, 12), r.randint(2, 10)
        return C(f"长方体长{a}厘米、宽{b}厘米、高{c}厘米，体积是（　）立方厘米。", numopts(a * b * c, [2 * (a * b + a * c + b * c), 4 * (a + b + c), a * b * c + a]))
    def surf(r):
        a, b, c = r.randint(2, 12), r.randint(2, 10), r.randint(2, 8)
        s = 2 * (a * b + a * c + b * c)
        return C(f"长方体长{a}分米、宽{b}分米、高{c}分米，表面积是（　）平方分米。", numopts(s, [a * b * c, a * b + a * c + b * c, 4 * (a + b + c)]))
    def cube(r):
        a = r.randint(2, 12)
        if r.random() < .5: return Fi(f"正方体棱长{a}厘米，体积是（　）立方厘米。", str(a ** 3))
        return Fi(f"正方体棱长{a}厘米，表面积是（　）平方厘米。", str(6 * a * a))
    def edges(r):
        a, b, c = r.randint(2, 15), r.randint(2, 12), r.randint(2, 10)
        return Fi(f"长方体长{a}厘米、宽{b}厘米、高{c}厘米，棱长总和是（　）厘米。", str(4 * (a + b + c)))
    def conv(r):
        k = r.randint(1, 9); t = r.choice([0, 1, 2, 3])
        if t == 0: return Fi(f"{k}立方米 = （　）立方分米", str(k * 1000))
        if t == 1: return Fi(f"{k}升 = （　）毫升", str(k * 1000))
        if t == 2: return Fi(f"{k}立方分米 = （　）升", str(k))
        return Fi(f"{k * 1000}立方厘米 = （　）立方分米", str(k))
    def h(r):
        a, b, c = r.randint(2, 10), r.randint(2, 10), r.randint(2, 10)
        return Fi(f"一个长方体体积是{a * b * c}立方米，底面是长{a}米、宽{b}米的长方形，高是（　）米。", str(c))
    facts = [("长方体有（　）个面。", "6"), ("长方体有（　）条棱。", "12"), ("长方体有（　）个顶点。", "8")]
    return [vol, surf, cube, edges, conv, h, fact(facts)]

def u5b_4():
    def simp(r):
        a, b = r.randint(1, 12), r.randint(2, 12); k = r.randint(2, 6)
        if gcd(a, b) != 1 or a >= b: return None
        return Fi(f"把{a * k}/{b * k}化成最简分数是（　）。", [f"{a}/{b}"])
    def tod(r):
        x = F(r.choice([1, 3, 1, 2, 3, 1, 7, 9]), r.choice([2, 4, 5, 10, 20, 25]))
        if x >= 1: return None
        return Fi(f"把{fs(x)}化成小数是（　）。", dec(x))
    def tof(r):
        k = r.choice([25, 75, 5, 4, 125, 6, 8, 35])
        x = F(k, 100 if k < 100 else 1000)
        return Fi(f"把{dec(x)}化成最简分数是（　）。", [fs(x)])
    def cmp(r):
        a, b, c, d = r.randint(1, 9), r.randint(2, 12), r.randint(1, 9), r.randint(2, 12)
        x, y = F(a, b), F(c, d)
        if a >= b or c >= d or x == y: return None
        return C(f"{a}/{b}和{c}/{d}，哪个大？", [f"{a}/{b}" if x > y else f"{c}/{d}", f"{c}/{d}" if x > y else f"{a}/{b}", "一样大", "无法比较"])
    def imp(r):
        w, a, b = r.randint(1, 5), r.randint(1, 6), r.randint(2, 8)
        if a >= b or gcd(a, b) != 1: return None
        return Fi(f"把带分数{w}又{a}/{b}化成假分数是（　）。", [f"{w * b + a}/{b}"])
    def mean(r):
        n, k = r.randint(3, 12), None
        k = r.randint(1, n - 1)
        return Fi(f"把一根3米长的绳子平均分成{n}段，{k}段占全长的（　）。（填分数）", [fs(F(k, n))] + ([f"{k}/{n}"] if gcd(k, n) != 1 else []))
    def kind(r):
        a, b = r.randint(1, 15), r.randint(2, 12)
        k = "真分数" if a < b else "假分数"
        return C(f"{a}/{b}是（　）。", [k, "假分数" if k == "真分数" else "真分数", "带分数", "整数"])
    return [simp, tod, tof, cmp, imp, mean, kind]

def u5b_5():
    facts = [("钟面上分针从12走到3，绕中心顺时针旋转了（　）°。", "90"),
             ("图形旋转后，（　）不变。", ["形状和大小", "位置", "方向", "位置和方向"]),
             ("旋转的三要素是旋转中心、旋转方向和（　）。", ["旋转角度", "旋转速度", "图形颜色", "图形大小"]),
             ("把一个图形绕一点旋转360°后，它会（　）。", ["回到原来位置", "变成原来的2倍", "上下颠倒", "左右颠倒"])]
    def clock(r):
        a = r.randint(1, 12); b = r.randint(1, 12)
        if a == b: return None
        return Fi(f"时针从“{a}”顺时针旋转（　）°到“{b}”。", str((b - a) % 12 * 30))
    def ccw(r):
        k = r.choice([90, 180, 270])
        return C(f"将一个图形绕点O顺时针旋转{k}°，相当于绕点O逆时针旋转（　）°。", numopts(360 - k, [k, 180 - k if k < 180 else k - 90, 360]))
    return [fact(facts), clock, ccw]

def u5b_6():
    def same(r):
        n = r.randint(3, 15); a, b = r.randint(1, n - 1), r.randint(1, n - 1)
        if a + b > n * 2: return None
        return Fi(f"{a}/{n} + {b}/{n} = ？（结果化成最简形式）", fans(F(a + b, n)))
    def diff(r):
        a, b = r.randint(1, 5), r.randint(2, 9); c, d = r.randint(1, 5), r.randint(2, 9)
        if a >= b or c >= d or b == d: return None
        x = F(a, b) + F(c, d); q = f"{a}/{b} + {c}/{d} = ？（结果化成最简形式）"
        if r.random() < .5: return Fi(q, fans(x))
        return C(q.replace("（结果化成最简形式）", ""), [fs(x), f"{a + c}/{b + d}", f"{a + c}/{b * d}", fs(x + F(1, b * d))])
    def sub(r):
        a, b = r.randint(1, 5), r.randint(2, 9); c, d = r.randint(1, 5), r.randint(2, 9)
        x, y = F(a, b), F(c, d)
        if a >= b or c >= d or x <= y: return None
        return Fi(f"{a}/{b} - {c}/{d} = ？（结果化成最简形式）", fans(x - y))
    def one(r):
        a, b = r.randint(1, 8), r.randint(2, 9)
        if a >= b: return None
        return Fi(f"1 - {a}/{b} = ？", fans(1 - F(a, b)))
    def word(r):
        a, b = r.randint(1, 4), r.randint(5, 9); c = r.randint(1, 4)
        if gcd(a, b) != 1 or gcd(c, b + 1) != 1: return None
        x = F(a, b) + F(c, b + 1)
        if x >= 1: return None
        return Fi(f"一项工程，第一天完成了{a}/{b}，第二天完成了{c}/{b + 1}，两天共完成了这项工程的几分之几？", fans(x))
    return [same, diff, sub, one, word]

def u5b_7():
    facts = [("要表示气温的变化情况，最好选用（　）统计图。", ["折线", "条形", "扇形", "以上都不行"]),
             ("要比较各班人数的多少，最好选用（　）统计图。", ["条形", "折线", "扇形", "以上都不行"]),
             ("折线统计图不但可以表示数量的多少，还能清楚地看出数量的（　）。", ["增减变化", "部分与整体的关系", "平均数", "最大公因数"])]
    def rise(r):
        vals = [r.randint(10, 40) for _ in range(5)]
        diffs = [vals[i + 1] - vals[i] for i in range(4)]
        i = max(range(4), key=lambda k: diffs[k])
        if diffs.count(diffs[i]) > 1 or diffs[i] <= 0: return None
        days = ["周一", "周二", "周三", "周四", "周五"]
        opts = [f"{days[i]}到{days[i + 1]}"] + [f"{days[j]}到{days[j + 1]}" for j in range(4) if j != i]
        return C("折线统计图显示某周五天的气温分别是" + "、".join(f"{v}℃" for v in vals) + "，气温上升最多的是（　）。", opts)
    def diff(r):
        a, b = r.randint(10, 60), r.randint(10, 60)
        if a == b: return None
        return Fi(f"复式折线统计图中，3月甲店卖出{a}台，乙店卖出{b}台，两店相差（　）台。", str(abs(a - b)))
    return [fact(facts), rise, diff]

def u5b_8():
    def times(r):
        n = r.choice([3, 4, 5, 8, 9, 10, 12, 20, 27, 28, 81])
        k, m = 0, 1
        while m < n: m *= 3; k += 1
        return C(f"有{n}个零件，其中1个是次品（稍轻），用天平至少称（　）次能保证找出次品。", numopts(k, [k + 1, n - 1, n // 2]))
    def first(r):
        return C("找次品时，把待测物品分成（　）份，通常能使称的次数最少。", ["3", "2", "4", "5"])
    return [times, first]

def vol_g5b():
    return [("第一单元 观察物体（三）", u5b_1()), ("第二单元 因数与倍数", u5b_2()), ("第三单元 长方体和正方体", u5b_3()),
            ("第四单元 分数的意义和性质", u5b_4()), ("第五单元 图形的运动（三）", u5b_5()),
            ("第六单元 分数的加法和减法", u5b_6()), ("第七单元 折线统计图", u5b_7()),
            ("第八单元 数学广角——找次品", u5b_8())]

# =====================================================================
# 6上
# =====================================================================
def u6a_1():
    def pair(r):
        c, rw = r.randint(1, 9), r.randint(1, 9)
        if c == rw: return None
        return C(f"{r.choice(NAMES)}坐在第{c}列第{rw}行，用数对表示是（　）。", [f"({c},{rw})", f"({rw},{c})", f"({c},{c})", f"({rw},{rw})"])
    def move(r):
        x, y, a = r.randint(1, 8), r.randint(1, 8), r.randint(1, 5)
        d = r.choice(["右", "上"])
        nx, ny = (x + a, y) if d == "右" else (x, y + a)
        return Fi(f"点A的位置是({x},{y})，向{d}平移{a}格后，位置是（　）。（写成(x,y)形式）", [f"({nx},{ny})", f"（{nx},{ny}）", f"({nx}，{ny})", f"{nx},{ny}"])
    def same(r):
        x = r.randint(1, 9)
        return C(f"数对({x},3)和({x},7)表示的两个位置在同一（　）。", ["列", "行", "斜线", "无法判断"])
    def opp(r):
        dirs = [("北", "南"), ("东", "西")]
        a = r.choice([10, 20, 25, 30, 35, 40, 50, 60, 70])
        p, q = r.choice([("北", "东"), ("北", "西"), ("南", "东"), ("南", "西")])
        op = {"北": "南", "南": "北", "东": "西", "西": "东"}
        right = f"{op[p]}偏{op[q]}{a}°"
        return C(f"学校在小明家{p}偏{q}{a}°方向，那么小明家在学校的（　）方向。", [right, f"{p}偏{q}{a}°", f"{op[p]}偏{op[q]}{90 - a}°" if a != 45 else f"{q}偏{p}{a}°", f"{op[q]}偏{op[p]}{a}°"])
    def dist(r):
        s, cm = r.choice([100, 200, 500, 1000]), r.randint(2, 8)
        return Fi(f"在地图上，1厘米表示实际距离{s}米。学校到书店的图上距离是{cm}厘米，实际距离是（　）米。", str(s * cm))
    return [pair, move, same, opp, dist]

def u6a_2():
    def fi(r):
        a, b, c = r.randint(1, 8), r.randint(2, 12), r.randint(2, 20)
        if a >= b: return None
        x = F(a, b) * c
        return Fi(f"{a}/{b} × {c} = ？（结果化成最简形式）", fans(x))
    def ff(r):
        a, b, c, d = r.randint(1, 8), r.randint(2, 10), r.randint(1, 8), r.randint(2, 10)
        if a >= b or c >= d: return None
        x = F(a, b) * F(c, d); q = f"{a}/{b} × {c}/{d} = ？"
        if r.random() < .5: return Fi(q + "（结果化成最简形式）", fans(x))
        return C(q, [fs(x), f"{a * c}/{b + d}", f"{a + c}/{b * d}", fs(F(a * d, b * c)) if F(a * d, b * c) != x else fs(x * 2)])
    def part(r):
        a, b = r.randint(1, 5), r.randint(2, 9); k = r.randint(2, 12)
        if a >= b: return None
        tot = b * k
        return Fi(f"一桶油重{tot}千克，用去了它的{a}/{b}，用去了多少千克？", str(a * k))
    def more(r):
        a, b = r.randint(1, 4), r.randint(3, 9); k = r.randint(5, 20)
        if a >= b: return None
        base = b * k
        return C(f"某村去年产粮{base}吨，今年比去年增产{a}/{b}，今年产粮多少吨？", numopts(base + a * k, [a * k, base - a * k, base + a]))
    def less(r):
        a, b = r.randint(1, 4), r.randint(3, 9); k = r.randint(5, 20)
        if a >= b: return None
        base = b * k
        return Fi(f"一件衣服原价{base}元，现在比原价降低了{a}/{b}，现价是多少元？", str(base - a * k))
    def cmpk(r):
        a = r.randint(10, 99); b, c = r.randint(1, 5), r.randint(6, 9)
        return C(f"不计算，比较大小：{a} × {b}/{c} ○ {a}", ["<", ">", "=", "无法比较"])
    def mix(r):
        a, b = r.randint(1, 4), r.randint(2, 9); x = F(r.randint(1, 9), 10)
        if a >= b: return None
        return Fi(f"{a}/{b} × {dec(x)} = ？（用分数或小数表示）", fans(F(a, b) * x))
    def law(r):
        a, b = r.randint(1, 5), r.choice([4, 6, 8, 12]); c = r.randint(1, 5); d = b
        if a >= b or c >= d: return None
        k = r.choice([24, 48, 36, 72])
        if k % b: return None
        x = (F(a, b) + F(c, d)) * k
        return Fi(f"简便计算：({a}/{b} + {c}/{d}) × {k} = ？", fans(x))
    return [fi, ff, part, more, less, cmpk, mix, law]

def u6a_3():
    def rec(r):
        a, b = r.randint(1, 12), r.randint(1, 12)
        if a == b: return None
        x = F(a, b)
        return Fi(f"{fs(x)}的倒数是（　）。", fans(1 / x))
    def div(r):
        a, b, c, d = r.randint(1, 8), r.randint(2, 10), r.randint(1, 8), r.randint(2, 10)
        if a >= b or c >= d: return None
        x = F(a, b) / F(c, d); q = f"{a}/{b} ÷ {c}/{d} = ？"
        if r.random() < .5: return Fi(q + "（结果化成最简形式）", fans(x))
        w1 = F(a, b) * F(c, d); w2 = F(b, a) * F(c, d)
        return C(q, [fs(x), fs(w1) if w1 != x else fs(x + 1), fs(w2) if w2 != x and w2 != w1 else fs(x * 2), fs(F(a, d))])
    def divint(r):
        a, b, c = r.randint(1, 9), r.randint(2, 12), r.randint(2, 9)
        if a >= b: return None
        return Fi(f"{a}/{b} ÷ {c} = ？（结果化成最简形式）", fans(F(a, b) / c))
    def intdiv(r):
        a, b, c = r.randint(1, 5), r.randint(2, 9), r.randint(2, 20)
        if a >= b: return None
        return Fi(f"{c} ÷ {a}/{b} = ？", fans(c / F(a, b)))
    def whole(r):
        a, b = r.randint(1, 5), r.randint(2, 9); k = r.randint(2, 15)
        if a >= b: return None
        part = a * k
        return C(f"一个数的{a}/{b}是{part}，这个数是多少？", numopts(b * k, [F(part * a, b), part, part + b]))
    def word(r):
        a, b = r.randint(1, 4), r.randint(3, 9); k = r.randint(3, 15)
        if a >= b: return None
        whole_ = b * k; more = whole_ + a * k
        return Fi(f"今年小麦产量是{more}吨，比去年增产{a}/{b}，去年产量是多少吨？", str(whole_))
    facts = [("1的倒数是（　）。", "1"), ("0（　）倒数。", ["没有", "有", "的倒数是0", "的倒数是1"]),
             ("乘积是（　）的两个数互为倒数。", "1")]
    return [rec, div, divint, intdiv, whole, word, fact(facts)]

def u6a_neg():
    def temp(r):
        hi, lo = r.randint(1, 15), r.randint(1, 15)
        return Fi(f"某地白天最高气温是{hi}℃，夜间最低气温是-{lo}℃，这天的温差是（　）℃。", str(hi + lo))
    def cmp(r):
        a, b = r.randint(-20, 20), r.randint(-20, 20)
        if a == b: return None
        return C(f"{a}和{b}，哪个大？", [str(max(a, b)), str(min(a, b)), "一样大", "无法比较"])
    def mean(r):
        k = r.randint(50, 500)
        return C(f"如果收入{k}元记作+{k}元，那么支出{k}元记作（　）。", [f"-{k}元", f"+{k}元", f"{k}元", "0元"])
    facts = [("0（　）。", ["既不是正数也不是负数", "是正数", "是负数", "是最小的数"]),
             ("在数轴上，-3在-1的（　）边。", ["左", "右", "上", "下"])]
    def sea(r):
        a, b = r.randint(100, 3000), r.randint(10, 200)
        return Fi(f"一座山高出海平面{a}米，记作+{a}米；一处海沟低于海平面{b}米，记作（　）米。", [f"-{b}"])
    return [temp, cmp, mean, fact(facts), sea]

def u6a_4():
    def circ(r):
        rr = r.randint(1, 20)
        c = 2 * PI * rr
        q = f"一个圆的半径是{rr}厘米，它的周长是（　）厘米。（π取3.14）"
        return C(q, numopts(c, [PI * rr, PI * rr * rr, c * 2]))
    def circd(r):
        d = r.randint(2, 30)
        return Fi(f"一个圆的直径是{d}米，它的周长是（　）米。（π取3.14）", dec(PI * d))
    def area(r):
        rr = r.randint(1, 15)
        a = PI * rr * rr
        return C(f"一个圆的半径是{rr}分米，它的面积是（　）平方分米。（π取3.14）", numopts(a, [2 * PI * rr, PI * rr * 2 * rr * 2, PI * rr]))
    def aread(r):
        d = r.randrange(2, 21, 2)
        return Fi(f"一个圆的直径是{d}厘米，它的面积是（　）平方厘米。（π取3.14）", dec(PI * (d // 2) ** 2))
    def ring(r):
        R, rr = r.randint(3, 12), r.randint(1, 10)
        if rr >= R: return None
        return Fi(f"一个圆环，外圆半径{R}厘米，内圆半径{rr}厘米，圆环面积是（　）平方厘米。（π取3.14）", dec(PI * (R * R - rr * rr)))
    def rad(r):
        rr = r.randint(1, 15)
        c = 2 * PI * rr
        return Fi(f"一个圆的周长是{dec(c)}米，它的半径是（　）米。（π取3.14）", str(rr))
    def dr(r):
        rr = r.randint(1, 50)
        return Fi(f"同一个圆里，半径是{rr}厘米，直径是（　）厘米。", str(2 * rr))
    def scale(r):
        k = r.choice([2, 3, 4])
        return C(f"一个圆的半径扩大到原来的{k}倍，它的面积扩大到原来的（　）倍。", numopts(k * k, [k, 2 * k, k * k * k]))
    def wheel(r):
        d, n = F(r.choice([5, 6, 7, 8]), 10), r.randint(10, 100)
        return Fi(f"一个车轮直径是{dec(d)}米，滚动{n}圈前进了（　）米。（π取3.14）", dec(PI * d * n))
    def sector(r):
        rr, ang = r.randint(2, 10), r.choice([90, 180, 120, 60])
        return Fi(f"半径{rr}厘米、圆心角{ang}°的扇形面积是（　）平方厘米。（π取3.14）", dec(PI * rr * rr * ang / 360)) if is_term(PI * rr * rr * ang / 360) else None
    facts = [("圆的周长与直径的比值叫作（　）。", ["圆周率", "半径", "直径", "面积"]),
             ("圆有（　）条对称轴。", ["无数", "1", "2", "4"]),
             ("画圆时，圆规两脚间的距离是圆的（　）。", ["半径", "直径", "周长", "面积"])]
    return [circ, circd, area, aread, ring, rad, dr, scale, wheel, sector, fact(facts)]

def u6a_5():
    def f2p(r):
        x = F(r.randint(1, 19), 20)
        return Fi(f"把{fs(x)}化成百分数是（　）。", [dec(x * 100) + "%"])
    def d2p(r):
        x = F(r.randint(1, 300), 1000)
        return Fi(f"把{dec(x)}化成百分数是（　）。", [dec(x * 100) + "%"])
    def p2d(r):
        p = r.randint(1, 250)
        return C(f"{p}%化成小数是（　）。", [dec(F(p, 100)), dec(F(p, 10)), dec(F(p, 1000)), str(p)])
    def rate(r):
        tot = r.choice([40, 50, 25, 20, 80]); ok = r.randint(tot // 2, tot)
        return Fi(f"某班有{tot}人，今天出勤{ok}人，出勤率是（　）。", [dec(F(ok, tot) * 100) + "%"])
    def ofp(r):
        n, p = r.choice([200, 300, 400, 500, 800, 1200]), r.choice([10, 20, 25, 30, 40, 45, 60, 75])
        return Fi(f"{n}的{p}%是（　）。", dec(F(n * p, 100)))
    def more(r):
        a, p = r.choice([200, 400, 500, 800]), r.choice([10, 20, 25, 30, 50])
        b = a + a * p // 100
        return C(f"原价{a}元，现价比原价提高了{p}%，现价是多少元？", numopts(b, [a * p // 100, a - a * p // 100, a + p]))
    def pct(r):
        a, b = r.choice([(20, 25), (30, 40), (45, 60), (12, 16), (40, 50), (30, 25)])
        x = F(a - b, b) * 100
        word = "多" if a > b else "少"
        return Fi(f"{a}比{b}{word}百分之几？", [dec(abs(x)) + "%"]) if is_term(x) else None
    def back(r):
        p, part = r.choice([20, 25, 40, 50, 75]), None
        whole = r.choice([80, 120, 200, 400])
        part = whole * p // 100
        return Fi(f"一个数的{p}%是{part}，这个数是（　）。", str(whole))
    def cmp(r):
        a = F(r.randint(1, 99), 100); b = F(r.randint(1, 9), 10)
        if a == b: return None
        return C(f"{dec(a * 100)}%和{dec(b)}，哪个大？", [dec(a * 100) + "%" if a > b else dec(b), dec(b) if a > b else dec(a * 100) + "%", "一样大", "无法比较"])
    return [f2p, d2p, p2d, rate, ofp, more, pct, back, cmp]

def u6a_6():
    def pig(r):
        n = r.randint(2, 9); k = r.randint(1, 4); m = n * k + r.randint(1, n - 1) if n > 1 else n + 1
        ans = -(-m // n)
        return C(f"把{m}个苹果放进{n}个抽屉里，总有一个抽屉至少放进（　）个苹果。", numopts(ans, [m // n if m // n != ans else ans + 1, ans + 1, n]))
    def mix(r):
        a, b, c = r.randint(1, 5), r.choice([4, 6, 8, 10]), r.randint(10, 40)
        if a >= b: return None
        return Fi(f"{c} × {a}/{b} + {c} × {b - a}/{b} = ？", str(c))
    return [pig, mix, u6a_2()[1], u6a_3()[1], u6a_4()[0], u6a_5()[4]]

def vol_g6a():
    return [("第一单元 确定位置", u6a_1()), ("第二单元 分数乘法", u6a_2()), ("第三单元 分数除法", u6a_3()),
            ("综合与实践 生活中的负数", u6a_neg()), ("第四单元 圆", u6a_4()), ("第五单元 百分数", u6a_5()),
            ("第六单元 复习与关联", u6a_6())]

# =====================================================================
# 6下 (provisional)
# =====================================================================
def u6b_1(): return u6a_neg()

def u6b_2():
    def disc(r):
        p, k = r.choice([100, 200, 240, 300, 360, 500, 800]), r.choice([7, 8, 9, 6, 75, 85])
        rate = F(k, 10) if k < 10 else F(k, 100)
        name = f"{k}折" if k < 10 else f"{k // 10}{k % 10 if k % 10 else ''}折".replace("75折", "七五折").replace("85折", "八五折")
        return Fi(f"一件商品原价{p}元，打{name}出售，现价是（　）元。", dec(p * rate))
    def interest(r):
        P, y = r.choice([1000, 2000, 5000, 10000]), r.choice([1, 2, 3])
        rate = r.choice([F(15, 1000), F(2, 100), F(275, 10000), F(3, 100)])
        it = P * rate * y
        return Fi(f"把{P}元存入银行，定期{y}年，年利率{dec(rate * 100)}%，到期时可得利息（　）元。", dec(it))
    def tax(r):
        a, t = r.choice([2000, 5000, 8000, 10000]), r.choice([3, 5, 6, 13])
        return Fi(f"某商店营业额{a}元，按{t}%缴纳税款，应缴税（　）元。", dec(F(a * t, 100)))
    def cheng(r):
        a, k = r.choice([100, 200, 500, 1000]), r.randint(1, 4)
        return C(f"某农场去年产粮{a}吨，今年比去年增产{CN[k]}成，今年产粮（　）吨。", numopts(a + a * k // 10, [a * k // 10, a - a * k // 10, a + k]))
    def back(r):
        p, k = r.choice([60, 80, 120, 160, 240]), r.choice([8, 75])
        rate = F(k, 10) if k < 10 else F(k, 100)
        name = "八折" if k == 8 else "七五折"
        orig = p / rate
        return Fi(f"一件衣服打{name}后售价{p}元，原价是（　）元。", dec(orig)) if is_term(orig) else None
    return [disc, interest, tax, cheng, back]

def u6b_3():
    def cyl_v(r):
        rr, h = r.randint(1, 10), r.randint(2, 20)
        v = PI * rr * rr * h
        return C(f"圆柱底面半径{rr}厘米，高{h}厘米，体积是（　）立方厘米。（π取3.14）", numopts(v, [v / 3, 2 * PI * rr * h, PI * rr * h]))
    def cyl_s(r):
        rr, h = r.randint(1, 8), r.randint(2, 15)
        return Fi(f"圆柱底面半径{rr}分米，高{h}分米，侧面积是（　）平方分米。（π取3.14）", dec(2 * PI * rr * h))
    def cyl_t(r):
        rr, h = r.randint(1, 6), r.randint(2, 12)
        return Fi(f"圆柱底面半径{rr}米，高{h}米，表面积是（　）平方米。（π取3.14）", dec(2 * PI * rr * h + 2 * PI * rr * rr))
    def cone(r):
        rr, h = r.randint(1, 10), r.randrange(3, 31, 3)
        v = PI * rr * rr * h / 3
        return C(f"圆锥底面半径{rr}厘米，高{h}厘米，体积是（　）立方厘米。（π取3.14）", numopts(v, [v * 3, v * 2, PI * rr * h]))
    def rel(r):
        v = r.randint(3, 60) * 3
        k = r.choice([0, 1])
        if k == 0: return Fi(f"等底等高的圆柱和圆锥，圆柱体积是{v}立方厘米，圆锥体积是（　）立方厘米。", str(v // 3))
        return Fi(f"等底等高的圆柱和圆锥，体积相差{v}立方分米，圆柱体积是（　）立方分米。", dec(F(v * 3, 2)))
    facts = [("圆柱的侧面展开后，可能是（　）。", ["长方形或正方形或平行四边形", "圆", "三角形", "扇形"]),
             ("圆锥有（　）条高。", ["1", "无数", "2", "0"])]
    return [cyl_v, cyl_s, cyl_t, cone, rel, fact(facts)]

def u6b_4():
    def ratio(r):
        a, b = r.randint(1, 9), r.randint(1, 9); k = r.randint(2, 12)
        if gcd(a, b) != 1 or a == b: return None
        return Fi(f"化简比：{a * k}∶{b * k} = （　）（用∶号）", [f"{a}∶{b}", f"{a}:{b}"])
    def val(r):
        a, b = r.randint(1, 20), r.randint(1, 20)
        return Fi(f"{a}∶{b}的比值是（　）。", fans(F(a, b)))
    def share(r):
        a, b = r.randint(1, 5), r.randint(1, 5); k = r.randint(5, 30)
        if a == b: return None
        tot = (a + b) * k
        return C(f"把{tot}本书按{a}∶{b}分给甲、乙两班，甲班分得（　）本。", numopts(a * k, [b * k, tot // 2, a * tot // b if (a * tot) % b == 0 else a * k + 1]))
    def solve(r):
        a, b, c = r.randint(1, 9), r.randint(1, 9), r.randint(1, 9)
        x = F(b * c, a)
        return Fi(f"解比例：{a}∶{b} = {c}∶x，x = （　）", fans(x))
    def sc(r):
        s, cm = r.choice([10000, 50000, 100000, 2000000, 500000]), r.randint(2, 9)
        km = F(s * cm, 100000)
        return Fi(f"一幅地图的比例尺是1∶{s}，图上距离{cm}厘米，实际距离是（　）千米。", dec(km))
    def prop(r):
        k = r.choice([0, 1, 2, 3])
        qs = [("速度一定，路程和时间成（　）比例。", "正"), ("路程一定，速度和时间成（　）比例。", "反"),
              ("单价一定，总价和数量成（　）比例。", "正"), ("总价一定，单价和数量成（　）比例。", "反")]
        q, a = qs[k]
        return C(q, [a, "反" if a == "正" else "正", "不成", "无法判断"])
    def zheng(r):
        a, b, c = r.randint(2, 6), r.randint(10, 50), r.randint(3, 12)
        return Fi(f"买{a}支同样的笔用了{a * b}元，照这样计算，买{c}支要（　）元。（用比例解）", str(b * c))
    return [ratio, val, share, solve, sc, prop, zheng]

def u6b_5(): return [u6a_6()[0]]

def vol_g6b():
    return [("第一单元 负数", u6b_1()), ("第二单元 百分数（二）", u6b_2()), ("第三单元 圆柱与圆锥", u6b_3()),
            ("第四单元 比例（含比）", u6b_4()), ("第五单元 数学广角——鸽巢问题", u6b_5()),
            ("第六单元 整理和复习", [u6a_2()[1], u6a_3()[1], u6a_5()[4], u6b_3()[0], u5b_2()[4]])]

VOLS = {"g1a": vol_g1a, "g1b": vol_g1b, "g2a": vol_g2a, "g2b": vol_g2b, "g3a": vol_g3a, "g3b": vol_g3b,
        "g4a": vol_g4a, "g4b": vol_g4b, "g5a": vol_g5a, "g5b": vol_g5b, "g6a": vol_g6a, "g6b": vol_g6b}
ORDER = ["g6a", "g1a", "g2a", "g3a", "g4a", "g5a", "g1b", "g2b", "g3b", "g4b", "g5b", "g6b"]

def build(vol):
    seed = 20261116 + ORDER.index(vol) * 101
    b = Bank(vol, seed)
    items = b.run(VOLS[vol](), total=84)
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, vol + ".json"), "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=1)
    return items

if __name__ == "__main__":
    vols = sys.argv[1:] or ORDER
    for v in vols:
        items = build(v)
        print(v, len(items))
