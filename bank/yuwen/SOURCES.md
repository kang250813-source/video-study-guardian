# 语文题库 (统编版小学语文) — sources & editions

Generated 2026-11-16 from the textbook full text below; every 古诗 line was copied programmatically from the text and re-checked by an independent validator.

## Source
- Fusyong/textbook-parser, https://github.com/Fusyong/textbook-parser/archive/refs/heads/main.zip
- Textbook text: `material/<batch>/*.md`; tables: `output/<batch>/bXY_{目录,识字表,写字表,词语表}.json`.

## Editions used
| File | Volume | Text used | Status |
|---|---|---|---|
| g1a–g6a | 一～六年级上册 | 2022课标修订版 (2026秋), `material/2026-09-16` | current |
| g1b–g3b | 一～三年级下册 | 2022课标修订版, `material/2026-04-02` | current |
| g4b | 四年级下册 | 2019版 text, `material/2026-04-02`, minus 颐和园, “诺曼底号”遇难记, 宝葫芦的秘密, 江畔独步寻花 (moved elsewhere in the revision) | **PROVISIONAL** |
| g5b | 五年级下册 | 2019版 text, 课文 only (no 日积月累 poems or sayings) | **PROVISIONAL** |
| g6b | 六年级下册 | 2019版 text, minus 两小儿辩日, 表里的生物, 他们那时候多有趣啊, 送元二使安西, 早春呈水部张十八员外, 江上渔者 | **PROVISIONAL** |

Provisional = the revised 4下/5下/6下 is not yet out; the 2019 text was trimmed with the known moves only. Other changes in the revision (new lessons, a different 日积月累) are not reflected. Rebuild these files when the revised text appears in textbook-parser.

Notes:
- 6下 清平乐 is 黄庭坚's「春归何处」 (taken from the text).
- 3上 山行 reads 「白云**生**处有人家」 in the revised 3上 text, and that is what the bank uses.
- 6上 (revised) contains 江畔独步寻花 and 送元二使安西 in 日积月累. 5上 (revised) contains 早春呈水部张十八员外 in 古诗三首. This matches the moves above.

## How content was built
- **古诗** (`topic: 古诗`): Every poem in 课文 and 语文园地·日积月累 was found by its author line (`[ 唐 ] …`, 汉乐府, 北朝民歌). Two poems with no author line, 画 (1上) and 迢迢牵牛星 / 采薇 (6下), were added by line range. Lines are copied from the textbook text by the script and split at ，。？！；. A few two-column layouts (mostly 词) use a fixed line range or column limit set in `FIX`/`EXTRA` in the script. No lines were typed in by hand. Question types: next line, previous line, author, which poem, plus 1–2 `fill` items per volume. Distractors come from other poem lines and titles of the same grade, picked to match the answer's length where possible.
- Skipped on purpose: 3上 舟夜书所见 (a 书写提示 example), 4上 浪淘沙（其七） (a 课后 reading exercise, not a recitation poem), 5下 日积月累 poems (游子吟, 鸟鸣涧, 凉州词, 黄鹤楼送孟浩然之广陵, 乡村四月).
- **综合**:
  - 生字读音: pinyin from 识字表/写字表. Only characters that are not marked polyphone and that pypinyin also gives exactly one reading for, matching the table. Distractors are tone variants of the same syllable, a common confusable (zh/z, n/l, -n/-ng, checked as a real syllable), or other characters' pinyin. Grade 6 has no pinyin in the source, so there are no pronunciation items for g6a/g6b.
  - 词语: blanks one character (preferably one from 写字表) of a 词语表 word. A distractor is rejected if it would form a real word (pypinyin phrase dictionary or any 词语表).
  - 日积月累: the second half of a saying (split at the last ，/；) as a choice question, and 4-character idiom lists as 选字补全成语.
- Each file has at most 120 questions. Extra 上一句 items were dropped first.

## Validation (all 12 files pass)
Valid UTF-8 JSON, ≥30 questions each, 4 distinct options, no duplicate `q`. Every 古诗 answer appears in that volume's text with whitespace, pinyin and note markers removed. For 9 lines of 词 printed in two columns (西江月 6上, 清平乐·村居 4下, 卜算子/浣溪沙 6下), the line is matched as an in-order run of characters within a short window rather than as one contiguous string.
