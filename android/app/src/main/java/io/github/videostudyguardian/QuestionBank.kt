package io.github.videostudyguardian

import android.content.res.AssetManager
import org.json.JSONArray
import java.text.Normalizer
import java.util.Locale
import kotlin.random.Random

/**
 * 题库：assets/bank/<科目>/g<年级><a=上册|b=下册>[_new|_old].json（构建时从仓库根目录 bank/ 复制）。
 * 选题规则与电脑版 questions.py / guardian.py 保持一致。
 */
class QuestionBank(private val assets: AssetManager) {

    data class Config(
        val grade: Int = 6,
        val term: String = "上",
        val mode: String = "全部",
        val subjects: List<String> = listOf("语文", "数学", "英语"),
        val englishEdition: String = "new",
    )

    /** 选择题：options 已打乱，right 为正确选项下标。填空题：answers 为可接受答案。 */
    data class Question(
        val type: String,
        val subject: String,
        val prompt: String,
        val options: List<String> = emptyList(),
        val right: Int = 0,
        val answers: List<String> = emptyList(),
    )

    private data class Item(val type: String, val subject: String, val topic: String, val prompt: String, val values: List<String>)

    companion object {
        val SUBJECT_DIRS = linkedMapOf("语文" to "yuwen", "数学" to "shuxue", "英语" to "yingyu")
        val MODES = mapOf("全部" to null, "背古诗" to "古诗", "背单词" to "单词")
        const val RECENT_LIMIT = 30

        /** 比较填空答案：忽略空格、大小写、全角/半角、弯引号（同 guardian.py normalize）。 */
        fun normalize(value: String): String {
            var text = Normalizer.normalize(value, Normalizer.Form.NFKC).trim().lowercase(Locale.ROOT)
            for ((a, b) in listOf("’" to "'", "‘" to "'", "…" to ".", "：" to ":")) {
                text = text.replace(a, b)
            }
            return text.filterNot { it.isWhitespace() }
        }
    }

    private val fileCache = HashMap<String, List<Item>>()
    private val listCache = HashMap<String, List<String>>()
    private val recent = ArrayList<String>()

    private fun listDir(folder: String): List<String> = listCache.getOrPut(folder) {
        try { assets.list("bank/$folder")?.toList() ?: emptyList() } catch (e: Exception) { emptyList() }
    }

    private fun files(subject: String, grade: Int, term: String, edition: String): List<String> {
        val folder = SUBJECT_DIRS[subject] ?: return emptyList()
        val names = listDir(folder)
        val stem = "g$grade${if (term == "上") "a" else "b"}"
        val preferred = "${stem}_$edition.json"
        if (preferred in names) return listOf("bank/$folder/$preferred")
        val plain = "$stem.json"
        if (plain in names) return listOf("bank/$folder/$plain")
        return names.filter { it.startsWith("${stem}_") && it.endsWith(".json") }.sorted().take(1).map { "bank/$folder/$it" }
    }

    private fun parse(path: String): List<Item> = fileCache.getOrPut(path) {
        try {
            val text = assets.open(path).bufferedReader(Charsets.UTF_8).use { it.readText() }
            val arr = JSONArray(text)
            val out = ArrayList<Item>(arr.length())
            for (i in 0 until arr.length()) {
                val o = arr.optJSONObject(i) ?: continue
                val type = o.optString("type")
                val key = if (type == "choice") "options" else if (type == "fill") "answers" else continue
                val values = o.optJSONArray(key) ?: continue
                val list = (0 until values.length()).map { values.optString(it) }
                if (list.isEmpty()) continue
                out.add(Item(type, o.optString("subject"), o.optString("topic"), o.optString("q"), list))
            }
            out
        } catch (e: Exception) {
            emptyList()
        }
    }

    private fun load(subject: String, grade: Int, term: String, edition: String): List<Item> =
        files(subject, grade, term, edition).flatMap { parse(it) }

    /** 按家长设置挑题：年级、上下册、科目、专题。找不到题时逐级放宽（同 questions.pool）。 */
    private fun pool(c: Config): List<Item> {
        val topic = MODES[c.mode]
        var subjects = c.subjects.filter { it in SUBJECT_DIRS }.ifEmpty { SUBJECT_DIRS.keys.toList() }
        if (topic == "古诗") subjects = listOf("语文") else if (topic == "单词") subjects = listOf("英语")
        val every = ArrayList<Item>()
        for (s in subjects) every += load(s, c.grade, c.term, c.englishEdition)
        val picked = every.filter { topic == null || it.topic == topic }
        if (picked.isNotEmpty()) return picked
        if (every.isNotEmpty()) return every
        // 本册没有（例如一二年级没有英语）：用全部科目兜底
        for (s in SUBJECT_DIRS.keys) every += load(s, c.grade, c.term, c.englishEdition)
        return every
    }

    fun count(c: Config): Int = pool(c).size

    /** 先随机选科目，再选题；最近 30 道不重复；选择题打乱选项。 */
    fun next(c: Config, random: Random = Random.Default): Question {
        var all = pool(c)
        if (all.isEmpty()) {
            all = listOf(Item("fill", "数学", "", "题库是空的，请家长检查题库。临时题：3 + 4 = ?", listOf("7")))
        }
        val fresh = all.filter { it.prompt !in recent }.ifEmpty { all }
        val subject = fresh.map { it.subject }.toSortedSet().toList().random(random)
        val item = fresh.filter { it.subject == subject }.random(random)
        recent.add(item.prompt)
        while (recent.size > RECENT_LIMIT) recent.removeAt(0)
        return if (item.type == "choice") {
            val order = item.values.indices.shuffled(random)
            Question("choice", item.subject, item.prompt, options = order.map { item.values[it] }, right = order.indexOf(0))
        } else {
            Question("fill", item.subject, item.prompt, answers = item.values)
        }
    }

    fun isCorrectFill(q: Question, input: String): Boolean {
        val n = normalize(input)
        return q.answers.any { normalize(it) == n }
    }
}
