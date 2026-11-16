package io.github.videostudyguardian

import java.security.MessageDigest
import java.security.SecureRandom
import javax.crypto.SecretKeyFactory
import javax.crypto.spec.PBEKeySpec

/** 管理员密码：PBKDF2-HMAC-SHA256 + 16 字节随机盐，只保存盐和哈希。请在后台线程调用。 */
object Password {
    const val ITERATIONS = 120_000
    const val MIN_LENGTH = 6

    private fun derive(password: String, salt: ByteArray, iterations: Int): ByteArray {
        val spec = PBEKeySpec(password.toCharArray(), salt, iterations, 256)
        try {
            return SecretKeyFactory.getInstance("PBKDF2WithHmacSHA256").generateSecret(spec).encoded
        } finally {
            spec.clearPassword()
        }
    }

    fun set(prefs: Prefs, password: String) {
        val salt = ByteArray(16).also { SecureRandom().nextBytes(it) }
        val digest = derive(password, salt, ITERATIONS)
        prefs.sp.edit()
            .putString("password_salt", salt.toHex())
            .putString("password_hash", digest.toHex())
            .putInt("password_iterations", ITERATIONS)
            .apply()
    }

    fun check(prefs: Prefs, password: String): Boolean {
        val salt = prefs.passwordSalt
        val hash = prefs.passwordHash
        if (salt.isEmpty() || hash.isEmpty() || password.isEmpty()) return false
        val candidate = derive(password, salt.fromHex(), prefs.passwordIterations)
        return MessageDigest.isEqual(candidate, hash.fromHex())
    }

    private fun ByteArray.toHex(): String = joinToString("") { "%02x".format(it.toInt() and 0xff) }

    private fun String.fromHex(): ByteArray = ByteArray(length / 2) { i ->
        substring(i * 2, i * 2 + 2).toInt(16).toByte()
    }
}
