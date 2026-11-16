"""题库加载：bank/<科目>/g<年级><a=上册|b=下册>[_new|_old].json

每道题是一个 JSON 对象：
  选择题 {"type":"choice","subject":"语文","topic":"古诗","unit":"…","q":"题干","options":["正确答案","干扰1","干扰2","干扰3"]}
  填空题 {"type":"fill","subject":"英语","topic":"单词","unit":"…","q":"题干","answers":["可接受答案", …]}
选择题的第一个选项永远是正确答案，显示时会打乱顺序。
"""
import json
from pathlib import Path

BANK_DIR = Path(__file__).resolve().parent / "bank"
SUBJECT_DIRS = {"语文": "yuwen", "数学": "shuxue", "英语": "yingyu"}
MODES = {"全部": None, "背古诗": "古诗", "背单词": "单词"}
DEFAULTS = {"grade": 6, "term": "上", "mode": "全部", "subjects": ["语文", "数学", "英语"], "english_edition": "new"}


def settings(config):
    s = dict(DEFAULTS)
    s.update({k: config[k] for k in DEFAULTS if k in config})
    return s


def _files(subject, grade, term, edition):
    folder = BANK_DIR / SUBJECT_DIRS[subject]
    stem = f"g{grade}{'a' if term == '上' else 'b'}"
    preferred = folder / f"{stem}_{edition}.json"
    if preferred.exists():
        return [preferred]
    plain = folder / f"{stem}.json"
    return [plain] if plain.exists() else sorted(folder.glob(f"{stem}_*.json"))[:1]


def load(subject, grade, term, edition="new"):
    items = []
    for f in _files(subject, grade, term, edition):
        try:
            items += json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
    return items


def pool(config):
    """按家长设置挑题：年级、上下册、科目、专题。找不到题时逐级放宽。"""
    s = settings(config)
    topic = MODES.get(s["mode"])
    subjects = [x for x in s["subjects"] if x in SUBJECT_DIRS] or list(SUBJECT_DIRS)
    if topic == "古诗":
        subjects = ["语文"]
    elif topic == "单词":
        subjects = ["英语"]
    every = []
    for subj in subjects:
        every += load(subj, s["grade"], s["term"], s["english_edition"])
    picked = [q for q in every if not topic or q.get("topic") == topic]
    if picked:
        return picked
    if every:
        return every
    # 本册没有（例如一二年级没有英语）：用全部科目兜底
    for subj in SUBJECT_DIRS:
        every += load(subj, s["grade"], s["term"], s["english_edition"])
    return every


def to_tuple(item):
    """转换成界面使用的格式。"""
    if item["type"] == "choice":
        return ("choice", item["subject"], item["q"], list(item["options"]), 0)
    return ("fill", item["subject"], item["q"], list(item["answers"]))
