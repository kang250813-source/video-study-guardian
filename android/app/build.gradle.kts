plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

// 题库在仓库根目录的 bank/，构建时复制到 APK 的 assets/bank/（不提交副本，保持单一来源）
val bankSource = rootProject.layout.projectDirectory.dir("../bank")
val bankAssetsRoot = layout.buildDirectory.dir("generated/bankAssets")

val copyBank by tasks.registering(Sync::class) {
    from(bankSource) {
        include("**/*.json")
    }
    into(bankAssetsRoot.map { it.dir("bank") })
}

// 正式签名：只有在 CI 里提供了密钥库环境变量时才启用，否则使用调试签名
val releaseKeystore: String? = System.getenv("VSG_KEYSTORE_FILE")?.takeIf { it.isNotBlank() && file(it).exists() }

android {
    namespace = "io.github.videostudyguardian"
    compileSdk = 34

    defaultConfig {
        applicationId = "io.github.videostudyguardian"
        minSdk = 26
        targetSdk = 34
        versionCode = (System.getenv("VSG_VERSION_CODE") ?: "2").toInt()
        versionName = System.getenv("VSG_VERSION_NAME") ?: "1.0.1"
    }

    signingConfigs {
        if (releaseKeystore != null) {
            create("release") {
                storeFile = file(releaseKeystore)
                storePassword = System.getenv("VSG_KEYSTORE_PASSWORD")
                keyAlias = System.getenv("VSG_KEY_ALIAS")
                keyPassword = System.getenv("VSG_KEY_PASSWORD")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfig = if (releaseKeystore != null) signingConfigs.getByName("release") else signingConfigs.getByName("debug")
        }
    }

    sourceSets {
        getByName("main") {
            assets.srcDir(bankAssetsRoot.get().asFile)
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
    lint {
        abortOnError = false
        checkReleaseBuilds = false
    }
}

tasks.named("preBuild") { dependsOn(copyBank) }
