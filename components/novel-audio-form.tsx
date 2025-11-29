"use client"

import type React from "react"

import { useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Book, Headphones, CheckCircle2 } from "lucide-react"
import { createIndexedResource } from "@/lib/api"
import { useToast } from "@/components/ui/use-toast"

export function NovelAudioForm({ className = "" }: { className?: string } = {}) {
  const [title, setTitle] = useState("")
  const [type, setType] = useState<"novel" | "audio">("novel")
  const [telegramLink, setTelegramLink] = useState("")
  const [synced, setSynced] = useState(false)
  const [loading, setLoading] = useState(false)
  const { toast } = useToast()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!title.trim() || !telegramLink.trim()) {
      toast({
        title: "请填写完整信息",
        description: "标题与 Telegram 链接不能为空",
        variant: "destructive",
      })
      return
    }
    try {
      setLoading(true)
      const resource = await createIndexedResource({
        title: title.trim(),
        type,
        jump_url: telegramLink.trim(),
      })
    setSynced(true)
      toast({
        title: "索引成功",
        description: `已创建资源：${resource.title}`,
      })
    setTimeout(() => setSynced(false), 3000)
      setTitle("")
      setTelegramLink("")
    } catch (error) {
      const message = error instanceof Error ? error.message : "保存失败"
      toast({
        title: "保存失败",
        description: message,
        variant: "destructive",
      })
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-card-foreground">索引小说 / 音频</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-5">
          <div className="space-y-2">
            <Label htmlFor="title">标题</Label>
            <Input id="title" placeholder="输入资源标题..." value={title} onChange={(e) => setTitle(e.target.value)} />
          </div>

          <div className="space-y-2">
            <Label>资源类型</Label>
            <div className="flex gap-2">
              <Button
                type="button"
                variant={type === "novel" ? "default" : "outline"}
                onClick={() => setType("novel")}
                className="flex-1"
              >
                <Book className="h-4 w-4 mr-2" />
                小说
              </Button>
              <Button
                type="button"
                variant={type === "audio" ? "default" : "outline"}
                onClick={() => setType("audio")}
                className="flex-1"
              >
                <Headphones className="h-4 w-4 mr-2" />
                音频
              </Button>
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="link">Telegram 链接</Label>
            <Input
              id="link"
              placeholder="https://t.me/..."
              value={telegramLink}
              onChange={(e) => setTelegramLink(e.target.value)}
            />
          </div>

          <Button type="submit" className="w-full" disabled={loading}>
            保存并同步到频道
          </Button>

          {synced && (
            <Badge className="w-full justify-center py-2 bg-success text-success-foreground">
              <CheckCircle2 className="h-4 w-4 mr-2" />
              已同步到预览频道
            </Badge>
          )}
        </form>
      </CardContent>
    </Card>
  )
}
