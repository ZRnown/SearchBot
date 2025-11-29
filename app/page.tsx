"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { Sidebar } from "@/components/sidebar"
import { NovelAudioForm } from "@/components/novel-audio-form"
import { ComicUploadWizard } from "@/components/comic-upload-wizard"
import { ResourceList } from "@/components/resource-list"
import { SettingsDrawer } from "@/components/settings-drawer"
import { SearchButtonManager } from "@/components/search-button-manager"
import { UserManager } from "@/components/user-manager"
import { Button } from "@/components/ui/button"
import { useToast } from "@/components/ui/use-toast"

type NavItem = "novel-audio" | "comic" | "resources" | "buttons" | "users" | "settings"

interface Session {
  username: string
}

export default function Dashboard() {
  const [activeItem, setActiveItem] = useState<NavItem>("novel-audio")
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [session, setSession] = useState<Session | null>(null)
  const [checkingAuth, setCheckingAuth] = useState(true)
  const router = useRouter()
  const { toast } = useToast()

  useEffect(() => {
    let cancelled = false
    const check = async () => {
      try {
        const res = await fetch("/api/auth/session", { cache: "no-store" })
        if (!res.ok) {
          router.replace("/login")
          return
        }
        const data = (await res.json()) as Session
        if (!cancelled) {
          setSession(data)
        }
      } catch {
        router.replace("/login")
      } finally {
        if (!cancelled) {
          setCheckingAuth(false)
        }
      }
    }
    check()
    return () => {
      cancelled = true
    }
  }, [router])

  const handleLogout = async () => {
    await fetch("/api/auth/logout", { method: "POST" })
    toast({ title: "已退出登录" })
    router.replace("/login")
  }

  if (checkingAuth) {
    return (
      <div className="min-h-screen flex items-center justify-center text-muted-foreground">
        验证身份中...
      </div>
    )
  }

  return (
    <div className="flex min-h-screen bg-background">
      <Sidebar
        activeItem={activeItem}
        onItemChange={setActiveItem}
        collapsed={sidebarCollapsed}
        onCollapsedChange={setSidebarCollapsed}
        onLogout={handleLogout}
      />

      <main className="flex-1 overflow-auto flex justify-center">
        <div className="w-full p-6 lg:p-8 max-w-[90rem] mx-auto space-y-6">
          <header className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
            <h1 className="text-2xl font-bold text-foreground">
              {activeItem === "novel-audio" && "索引小说 / 音频"}
              {activeItem === "comic" && "上传漫画"}
              {activeItem === "resources" && "管理资源"}
                {activeItem === "buttons" && "搜索结果底部按钮"}
                {activeItem === "users" && "用户管理"}
              {activeItem === "settings" && "设置"}
            </h1>
            <p className="text-muted-foreground mt-1">
              {activeItem === "novel-audio" && "添加新的小说或有声书到你的 Telegram 机器人"}
              {activeItem === "comic" && "批量上传漫画图片"}
              {activeItem === "resources" && "查看和管理所有已索引的资源"}
                {activeItem === "buttons" && "自定义搜索回复下方的跳转按钮"}
                {activeItem === "users" && "查看所有使用机器人用户，并手动配置 VIP 权限"}
                {activeItem === "settings" && "配置机器人设置与账户安全"}
            </p>
            </div>
            <div className="flex items-center gap-3">
              {session && <span className="text-sm text-muted-foreground">👤 {session.username}</span>}
              <Button variant="outline" onClick={handleLogout}>
                退出登录
              </Button>
            </div>
          </header>

          {activeItem === "novel-audio" && <NovelAudioForm className="w-full" />}
          {activeItem === "comic" && <ComicUploadWizard className="w-full" />}
          {activeItem === "resources" && <ResourceList />}
          {activeItem === "buttons" && <SearchButtonManager />}
          {activeItem === "users" && <UserManager />}
          {activeItem === "settings" && <SettingsDrawer username={session?.username} />}
        </div>
      </main>
    </div>
  )
}
