"use client"

import { useEffect, useMemo, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Separator } from "@/components/ui/separator"
import { Copy, Link2, Plus, Save, Trash2 } from "lucide-react"
import {
  createSearchButton,
  deleteSearchButton,
  fetchSearchButtons,
  type SearchButtonRecord,
  updateSearchButton,
} from "@/lib/api"
import { useToast } from "@/components/ui/use-toast"

type EditState = Record<
  number,
  {
    label: string
    url: string
    sortOrder: string
    dirty: boolean
    saving: boolean
  }
>

export function SearchButtonManager() {
  const [buttons, setButtons] = useState<SearchButtonRecord[]>([])
  const [editMap, setEditMap] = useState<EditState>({})
  const [newLabel, setNewLabel] = useState("")
  const [newUrl, setNewUrl] = useState("")
  const [newOrder, setNewOrder] = useState("")
  const [loading, setLoading] = useState(false)
  const { toast } = useToast()

  useEffect(() => {
    let ignore = false
    const load = async () => {
      try {
        setLoading(true)
        const data = await fetchSearchButtons()
        if (!ignore) {
          setButtons(data)
          const draft: EditState = {}
          data.forEach((item) => {
            draft[item.id] = {
              label: item.label,
              url: item.url,
              sortOrder: String(item.sortOrder),
              dirty: false,
              saving: false,
            }
          })
          setEditMap(draft)
        }
      } catch (error) {
        toast({
          title: "读取按钮失败",
          description: error instanceof Error ? error.message : "网络异常",
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

  const nextSortOrder = useMemo(() => {
    if (!buttons.length) return 0
    return Math.max(...buttons.map((b) => b.sortOrder)) + 1
  }, [buttons])

  useEffect(() => {
    if (!newOrder) {
      setNewOrder(String(nextSortOrder))
    }
  }, [nextSortOrder, newOrder])

  const handleFieldChange = (id: number, field: keyof Pick<EditState[number], "label" | "url" | "sortOrder">, value: string) => {
    setEditMap((prev) => {
      const current = prev[id] ?? { label: "", url: "", sortOrder: "0", dirty: false, saving: false }
      return {
        ...prev,
        [id]: { ...current, [field]: value, dirty: true },
      }
    })
  }

  const persistRow = async (button: SearchButtonRecord) => {
    const state = editMap[button.id]
    if (!state || state.saving || !state.dirty) return
    if (!state.label.trim() || !state.url.trim()) {
      toast({ title: "请输入完整信息", variant: "destructive" })
      return
    }
    const sortOrder = Number(state.sortOrder)
    if (Number.isNaN(sortOrder)) {
      toast({ title: "排序必须是数字", variant: "destructive" })
      return
    }
    setEditMap((prev) => ({ ...prev, [button.id]: { ...state, saving: true } }))
    try {
      const updated = await updateSearchButton(button.id, {
        label: state.label.trim(),
        url: state.url.trim(),
        sort_order: sortOrder,
      })
      setButtons((prev) =>
        prev
          .map((item) => (item.id === updated.id ? updated : item))
          .sort((a, b) => a.sortOrder - b.sortOrder),
      )
      setEditMap((prev) => ({
        ...prev,
        [button.id]: {
          label: updated.label,
          url: updated.url,
          sortOrder: String(updated.sortOrder),
          dirty: false,
          saving: false,
        },
      }))
      toast({ title: "按钮已保存" })
    } catch (error) {
      toast({
        title: "保存失败",
        description: error instanceof Error ? error.message : "请稍后重试",
        variant: "destructive",
      })
      setEditMap((prev) => ({ ...prev, [button.id]: { ...state, saving: false } }))
    }
  }

  const handleAdd = async () => {
    if (!newLabel.trim() || !newUrl.trim()) {
      toast({ title: "请填写按钮文本和链接", variant: "destructive" })
      return
    }
    const sortOrder = Number(newOrder || nextSortOrder)
    if (Number.isNaN(sortOrder)) {
      toast({ title: "排序编号需为数字", variant: "destructive" })
      return
    }
    try {
      const created = await createSearchButton({
        label: newLabel.trim(),
        url: newUrl.trim(),
        sort_order: sortOrder,
      })
      setButtons((prev) => [...prev, created].sort((a, b) => a.sortOrder - b.sortOrder))
      setEditMap((prev) => ({
        ...prev,
        [created.id]: {
          label: created.label,
          url: created.url,
          sortOrder: String(created.sortOrder),
          dirty: false,
          saving: false,
        },
      }))
      setNewLabel("")
      setNewUrl("")
      setNewOrder(String(created.sortOrder + 1))
      toast({ title: "新增按钮成功" })
    } catch (error) {
      toast({
        title: "新增失败",
        description: error instanceof Error ? error.message : "请稍后再试",
        variant: "destructive",
      })
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await deleteSearchButton(id)
      setButtons((prev) => prev.filter((btn) => btn.id !== id))
      setEditMap((prev) => {
        const clone = { ...prev }
        delete clone[id]
        return clone
      })
      toast({ title: "已删除按钮" })
    } catch (error) {
      toast({
        title: "删除失败",
        description: error instanceof Error ? error.message : "请稍后再试",
        variant: "destructive",
      })
    }
  }

  const handleCopy = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text)
      toast({ title: "已复制到剪贴板" })
    } catch (error) {
      toast({
        title: "复制失败",
        description: error instanceof Error ? error.message : "浏览器未授权",
        variant: "destructive",
      })
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-card-foreground">
          <Link2 className="h-5 w-5" />
          搜索结果底部按钮
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="grid gap-4 sm:grid-cols-3">
          <div className="space-y-2">
            <Label htmlFor="new-label">按钮文本</Label>
            <Input
              id="new-label"
              placeholder="例如：联系客服"
              value={newLabel}
              onChange={(e) => setNewLabel(e.target.value)}
            />
          </div>
          <div className="space-y-2 sm:col-span-2">
            <Label htmlFor="new-url">按钮链接</Label>
            <Input
              id="new-url"
              placeholder="https://t.me/..."
              value={newUrl}
              onChange={(e) => setNewUrl(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="new-order">排序（越小越靠前）</Label>
            <Input
              id="new-order"
              type="number"
              value={newOrder}
              onChange={(e) => setNewOrder(e.target.value)}
            />
          </div>
        </div>
        <Button onClick={handleAdd} disabled={loading} className="w-full sm:w-auto">
          <Plus className="h-4 w-4 mr-2" />
          新增按钮
        </Button>

        <Separator />

        <div className="rounded-lg border border-border overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow className="bg-muted/50">
                <TableHead className="w-1/4">按钮文本</TableHead>
                <TableHead>跳转链接</TableHead>
                <TableHead className="w-24">排序</TableHead>
                <TableHead className="w-48 text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {buttons.map((button) => {
                const entry = editMap[button.id]
                return (
                  <TableRow key={button.id}>
                    <TableCell>
                      <Input
                        value={entry?.label ?? button.label}
                        onChange={(e) => handleFieldChange(button.id, "label", e.target.value)}
                      />
                    </TableCell>
                    <TableCell>
                      <Input
                        value={entry?.url ?? button.url}
                        onChange={(e) => handleFieldChange(button.id, "url", e.target.value)}
                      />
                    </TableCell>
                    <TableCell>
                      <Input
                        type="number"
                        value={entry?.sortOrder ?? String(button.sortOrder)}
                        onChange={(e) => handleFieldChange(button.id, "sortOrder", e.target.value)}
                      />
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-2">
                        <Button variant="secondary" size="icon" onClick={() => handleCopy(entry?.url ?? button.url)}>
                          <Copy className="h-4 w-4" />
                        </Button>
                        <Button
                          size="icon"
                          onClick={() => persistRow(button)}
                          disabled={!entry?.dirty || entry?.saving}
                        >
                          <Save className="h-4 w-4" />
                        </Button>
                        <Button variant="destructive" size="icon" onClick={() => handleDelete(button.id)}>
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                )
              })}
              {!buttons.length && (
                <TableRow>
                  <TableCell colSpan={4} className="text-center py-6 text-muted-foreground">
                    暂无按钮，请先添加
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  )
}

