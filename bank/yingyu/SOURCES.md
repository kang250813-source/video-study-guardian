# 英语题库来源说明（人教PEP 三起，3–6年级）

生成脚本：`src/gen_yingyu.py`（可重复运行，固定随机种子，输出稳定）。

## 版本对应
| 文件 | 册次 | 版本 | 单元标题来源 |
|---|---|---|---|
| g3a.json | 三年级上册 | 2024 新版 PEP | flyabc.fun |
| g3b.json | 三年级下册 | 2024 新版 PEP | flyabc.fun |
| g4a.json | 四年级上册 | 2024 新版 PEP | flyabc.fun |
| g4b.json | 四年级下册 | 2024 新版 PEP | flyabc.fun |
| g5a.json | 五年级上册 | 2024 新版 PEP | flyabc.fun |
| g5b.json | 五年级下册 | 2024 新版 PEP | flyabc.fun |
| g6a.json | 六年级上册 | 2024 新版 PEP（Unit 1 为 *Amazing places*，不是旧版 “How can I get there?”） | flyabc.fun |
| g6b_old.json | 六年级下册 | **旧版 PEP（临时替代）** | 教习网 l6b 单词表 |

## 六年级下册说明
截至生成时，2024 新版 PEP 六年级下册尚未出版（flyabc.fun 无 6b 词表）。g6b_old.json 使用**旧版** PEP 六下 4 个单元（How tall are you? / Last weekend / Where did you go? / Then and now）的单词和句型作为临时替代。新版六下出版后应替换。

## 数据来源
- 单词表（3a–6a，含中文释义）：https://flyabc.fun/words/{3a…6a}-u{1…6}（src/fly.json）
- 交叉核对（3a–5a）：速声英语 https://ss.aihu.cn/books/{pep3,pep3b,pep4,pep4b,pep5}/unit{N}（src/aihu.json）
- 旧版六下单词：教习网英语朗读 https://yyld.51jiaoxi.com 人教PEP六年级下册单词表（src/old6b.json）
- “综合”句型题：依据各单元 Let's talk 课文（https://yyld.51jiaoxi.com/{sanshang…liuxia}/rjbp_danyuanNN.html，src/yy_*.txt）编写（src/zonghe.py）

## 处理规则
- 3a 补充单词：and（和；与）、goodbye（再见）、toy（玩具）——Unit 1，见速声英语词表；piece（一块；一片）——按要求加入 Unit 6，**未在已抓取来源中找到，单元归属为推定**。
- 同一册重复出现的单词合并为一条，释义合并（如 orange＝橙子；橙色，cook＝做饭；厨师）。
- 释义中会泄露答案的标注被改写：如 “（young的比较级）更年轻的” → “更年轻的（比较级）”；6上 “去（过去式 went）” → “去”，并另出一道 “写出 go 的过去式” 填空题。
- 干扰项取自同一册（优先同单元），剔除与正确答案释义重叠或同义的词（如 mum/mother、listen/hear）。
- 填空题答案不区分大小写；含撇号/连字符的词另收 ’ 或空格写法。

## 已知差异
- 三上 Unit 3 标题：flyabc 与教习网为 “Our animal friends”，速声英语为 “Amazing animals”；采用前者。
