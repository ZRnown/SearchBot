"use client"

import { cn } from "@/lib/utils"
import { Book, Heart, Settings, List, Link2, Users, PanelLeftClose, PanelLeft } from "lucide-react"
import { Button } from "@/components/ui/button"

type NavItem = "novel-audio" | "comic" | "resources" | "buttons" | "users" | "settings"

interface SidebarProps {
  activeItem: NavItem
  onItemChange: (item: NavItem) => void
  collapsed: boolean
  onCollapsedChange: (collapsed: boolean) => void
  onLogout?: () => void
}

const navItems = [
  { id: "novel-audio" as const, label: "小说 / 音频", icon: Book },
  { id: "comic" as const, label: "漫画上传", icon: Heart },
  { id: "resources" as const, label: "资源管理", icon: List },
  { id: "buttons" as const, label: "搜索结果按钮", icon: Link2 },
  { id: "users" as const, label: "用户管理", icon: Users },
  { id: "settings" as const, label: "设置", icon: Settings },
]

export function Sidebar({ activeItem, onItemChange, collapsed, onCollapsedChange, onLogout }: SidebarProps) {
  return (
    <aside
      className={cn(
        "flex flex-col border-r border-border bg-sidebar h-screen transition-all duration-300 sticky top-0",
        collapsed ? "w-16" : "w-60",
      )}
    >
      <div className="flex items-center justify-between p-4 border-b border-border">
        {!collapsed && <span className="font-semibold text-sidebar-foreground text-balance">TG 资源管理器</span>}
        <Button
          variant="ghost"
          size="icon"
          onClick={() => onCollapsedChange(!collapsed)}
          className="text-sidebar-foreground"
        >
          {collapsed ? <PanelLeft className="h-5 w-5" /> : <PanelLeftClose className="h-5 w-5" />}
        </Button>
      </div>

      <nav className="flex-1 p-2 space-y-1">
        {navItems.map((item) => {
          const Icon = item.icon
          const isActive = activeItem === item.id
          return (
            <button
              key={item.id}
              onClick={() => onItemChange(item.id)}
              className={cn(
                "flex items-center gap-3 w-full px-3 py-2.5 rounded-lg text-sm font-medium transition-colors",
                isActive
                  ? "bg-sidebar-accent text-sidebar-primary"
                  : "text-sidebar-foreground hover:bg-sidebar-accent/50",
              )}
            >
              <Icon className="h-5 w-5 shrink-0" />
              {!collapsed && <span>{item.label}</span>}
            </button>
          )
        })}
      </nav>

      <div className="p-2 border-t border-border">
        <Button
          variant="ghost"
          className="w-full justify-center text-sm text-sidebar-foreground"
          onClick={onLogout}
          disabled={!onLogout}
        >
          退出登录
        </Button>
      </div>
    </aside>
  )
}
