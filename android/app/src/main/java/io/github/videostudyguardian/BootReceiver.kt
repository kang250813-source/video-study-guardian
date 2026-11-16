package io.github.videostudyguardian

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

/** 开机或应用更新后自动重新启动守护服务。 */
class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (Prefs(context).setupDone) {
            GuardService.start(context)
        }
    }
}
