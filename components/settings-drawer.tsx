"use client"

import { useEffect, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Settings, Save, Hash } from "lucide-react"
import { fetchSettings } from "@/lib/api"
import { useToast } from "@/components/ui/use-toast"

interface SettingsDrawerProps {
  username?: string | null
}

export function SettingsDrawer({ username }: SettingsDrawerProps) {
  const [pageSize, setPageSize] = useState("")
  const [channels, setChannels] = useState<
    { id: number; name: string }[]
  >([])
  const [loading, setLoading] = useState(true)
  const [currentPassword, setCurrentPassword] = useState("")
  const [newPassword, setNewPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [changingPassword, setChangingPassword] = useState(false)
  const { toast } = useToast()

  useEffect(() => {
    let ignore = false
    const load = async () => {
      try {
        setLoading(true)
        const data = await fetchSettings()
        if (!ignore) {
          setPageSize(String(data.pageSize))
          const entries = [
            { id: data.searchChannelId, name: "搜索群组 / 频道" },
            { id: data.storageChannelId, name: "漫画仓库频道" },
          ]
          setChannels(entries)
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : "加载失败"
        toast({
          title: "读取设置失败",
          description: message,
          variant: "destructive",
        })
      } finally {
        if (!ignore) {
          setLoading(false)
        }
      }
    }
    load()
    return () => {
      ignore = true
    }
  }, [toast])

  const handleSave = () => {
    toast({
      title: "暂未开放在线编辑",
      description: "如需修改参数，请暂时在 .env 中调整并重启服务。",
    })
  }

  const handlePasswordChange = async () => {
    if (!currentPassword || !newPassword) {
      toast({ title: "请填写完整信息", variant: "destructive" })
      return
    }
    if (newPassword.length < 8) {
      toast({ title: "新密码至少 8 位字符", variant: "destructive" })
      return
    }
    if (newPassword !== confirmPassword) {
      toast({ title: "两次输入的新密码不一致", variant: "destructive" })
      return
    }
    try {
      setChangingPassword(true)
      const res = await fetch("/api/auth/change-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.detail ?? "修改失败")
      }
      toast({ title: "密码修改成功" })
      setCurrentPassword("")
      setNewPassword("")
      setConfirmPassword("")
    } catch (error) {
      toast({
        title: "修改失败",
        description: error instanceof Error ? error.message : "请稍后再试",
        variant: "destructive",
      })
    } finally {
      setChangingPassword(false)
    }
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-card-foreground">
            <Settings className="h-5 w-5" />
            机器人设置
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="space-y-2">
            <Label htmlFor="page-size">每页数量</Label>
            <Input
              id="page-size"
              type="number"
              value={pageSize}
              onChange={(e) => setPageSize(e.target.value)}
              disabled={loading}
              placeholder="5"
            />
            <p className="text-xs text-muted-foreground">资源列表每页显示的项目数</p>
          </div>

          <Button onClick={handleSave} className="w-full" disabled={loading}>
            <Save className="h-4 w-4 mr-2" />
            保存设置
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-card-foreground">
            <Hash className="h-5 w-5" />
            已连接频道
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {channels.map((channel) => (
              <div key={channel.id} className="flex items-center justify-between p-3 rounded-lg bg-muted">
                <div>
                  <p className="font-medium text-sm">{channel.name}</p>
                  <p className="text-xs text-muted-foreground font-mono">{channel.id}</p>
                </div>
                <Badge variant="secondary" className="bg-success/10 text-success">
                  已连接
                </Badge>
              </div>
            ))}
            {!loading && channels.length === 0 && (
              <p className="text-sm text-muted-foreground">暂无频道信息</p>
            )}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-card-foreground">
            账户安全
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1">
            <Label>当前账户</Label>
            <p className="text-sm text-muted-foreground">{username ?? "管理员"}</p>
          </div>
          <div className="space-y-2">
            <Label htmlFor="current-password">当前密码</Label>
            <Input
              id="current-password"
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              autoComplete="current-password"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="new-password">新密码</Label>
            <Input
              id="new-password"
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              autoComplete="new-password"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="confirm-password">确认新密码</Label>
            <Input
              id="confirm-password"
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              autoComplete="new-password"
            />
          </div>
          <Button onClick={handlePasswordChange} disabled={changingPassword}>
            {changingPassword ? "更新中..." : "修改密码"}
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}
