"use client"

import React, { useEffect, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Book, Headphones, Heart, Crown, Search, ExternalLink, Trash2, Save, Copy, List } from "lucide-react"
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from "@/components/ui/pagination"
import { deleteResource, fetchResources, type ResourceRecord, updateResource, batchDeleteResources } from "@/lib/api"
import { useToast } from "@/components/ui/use-toast"
import { ComicFilesManager } from "./comic-files-manager"

type ResourceType = "all" | "novel" | "audio" | "comic"

const typeConfig = {
  novel: { icon: Book, label: "小说", className: "bg-primary/10 text-primary" },
  audio: { icon: Headphones, label: "音频", className: "bg-chart-2/10 text-chart-2" },
  comic: { icon: Heart, label: "漫画", className: "bg-chart-5/10 text-chart-5" },
}

const filterLabels: Record<ResourceType, string> = {
  all: "全部",
  novel: "小说",
  audio: "音频",
  comic: "漫画",
}

export function ResourceList() {
  const [filter, setFilter] = useState<ResourceType>("all")
  const [search, setSearch] = useState("")
  const [resources, setResources] = useState<ResourceRecord[]>([])
  const [loading, setLoading] = useState(false)
  const [page, setPage] = useState(1)
  const [totalCount, setTotalCount] = useState(0)
  const pageSize = 50
  const [editMap, setEditMap] = useState<
    Record<
      string,
      {
        title: string
        link: string
        dirty: boolean
        saving: boolean
      }
    >
  >({})
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [batchDeleteDialogOpen, setBatchDeleteDialogOpen] = useState(false)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [comicFilesManagerOpen, setComicFilesManagerOpen] = useState(false)
  const [selectedComicId, setSelectedComicId] = useState<string | null>(null)
  const { toast } = useToast()

  useEffect(() => {
    let ignore = false
    const load = async () => {
      try {
        setLoading(true)
        const skip = (page - 1) * pageSize
        const data = await fetchResources(filter, skip, pageSize)
        if (!ignore) {
          setResources(data)
          const nextMap: typeof editMap = {}
          data.forEach((item) => {
            nextMap[item.id] = {
              title: item.title,
              link: item.link,
              dirty: false,
              saving: false,
            }
          })
          setEditMap(nextMap)
        }
        // 获取总数
        const countResponse = await fetch(`/api/resources/count?${filter !== "all" ? `resource_type=${filter}` : ""}`)
        if (countResponse.ok) {
          const countData = await countResponse.json()
          if (!ignore) {
            setTotalCount(countData.count || 0)
          }
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : "加载失败"
        toast({
          title: "读取资源失败",
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
  }, [filter, page, toast])

  // 注意：搜索现在在客户端进行，但也可以改为服务端搜索
  // 由于使用了服务端分页，这里不需要客户端过滤
  const filteredResources = resources
  
  // 当筛选或搜索改变时，重置到第一页
  useEffect(() => {
    setPage(1)
  }, [filter, search])

  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      setSelectedIds(new Set(filteredResources.map((r) => r.id)))
    } else {
      setSelectedIds(new Set())
    }
  }

  const handleSelectOne = (id: string, checked: boolean) => {
    const next = new Set(selectedIds)
    if (checked) {
      next.add(id)
    } else {
      next.delete(id)
    }
    setSelectedIds(next)
  }

  const removeResource = async (id: string) => {
    try {
      await deleteResource(id)
      setResources((prev) => prev.filter((item) => item.id !== id))
      setEditMap((prev) => {
        const clone = { ...prev }
        delete clone[id]
        return clone
      })
      toast({ title: "已删除资源" })
    } catch (error) {
      const message = error instanceof Error ? error.message : "删除失败"
      toast({
        title: "删除失败",
        description: message,
        variant: "destructive",
      })
    }
  }

  const handleBatchDelete = async () => {
    if (selectedIds.size === 0) return
    try {
      await batchDeleteResources(Array.from(selectedIds))
      toast({ title: `已删除 ${selectedIds.size} 个资源` })
      setBatchDeleteDialogOpen(false)
      setResources((prev) => prev.filter((item) => !selectedIds.has(item.id)))
      setEditMap((prev) => {
        const clone = { ...prev }
        selectedIds.forEach((id) => delete clone[id])
        return clone
      })
      setSelectedIds(new Set())
    } catch (error) {
      const message = error instanceof Error ? error.message : "批量删除失败"
      toast({
        title: "批量删除失败",
        description: message,
        variant: "destructive",
      })
    }
  }

  const handleCopyDeepLink = async (resource: ResourceRecord) => {
    const link = resource.deepLink ?? resource.link
    if (!link) {
      toast({ title: "没有可复制的链接", variant: "destructive" })
      return
    }
    try {
      await navigator.clipboard.writeText(link)
      toast({ title: "深度链接已复制" })
    } catch (error) {
      toast({
        title: "复制失败",
        description: error instanceof Error ? error.message : "浏览器未授权",
        variant: "destructive",
      })
    }
  }

  const handleFieldChange = (id: string, field: "title" | "link", value: string) => {
    setEditMap((prev) => {
      const current = prev[id] ?? {
        title: "",
        link: "",
        dirty: false,
        saving: false,
      }
      return {
        ...prev,
        [id]: {
          ...current,
          [field]: value,
          dirty: true,
        },
      }
    })
  }

  const handleRowSave = async (resource: ResourceRecord) => {
    const entry = editMap[resource.id]
    if (!entry || entry.saving || !entry.dirty) {
      return
    }
    if (!entry.title.trim() || !entry.link.trim()) {
      toast({ title: "请填写完整信息", variant: "destructive" })
      return
    }
    try {
      setEditMap((prev) => ({
        ...prev,
        [resource.id]: { ...entry, saving: true },
      }))
      const payload: { title?: string; jump_url?: string; preview_url?: string } = {
        title: entry.title.trim(),
      }
      if (resource.type === "comic") {
        payload.preview_url = entry.link.trim()
      } else {
        payload.jump_url = entry.link.trim()
      }
      const updated = await updateResource(resource.id, payload)
      setResources((prev) =>
        prev.map((item) => (item.id === updated.id ? updated : item)),
      )
      setEditMap((prev) => ({
        ...prev,
        [resource.id]: {
          title: updated.title,
          link: updated.link,
          dirty: false,
          saving: false,
        },
      }))
      toast({ title: "已更新资源" })
    } catch (error) {
      const message = error instanceof Error ? error.message : "更新失败"
      toast({
        title: "更新失败",
        description: message,
        variant: "destructive",
      })
      setEditMap((prev) => ({
        ...prev,
        [resource.id]: { ...entry, saving: false },
      }))
    }
  }

  return (
    <>
      <Card className="w-full">
      <CardHeader>
        <CardTitle className="text-card-foreground">资源列表</CardTitle>
        <div className="flex flex-col sm:flex-row gap-3 mt-4">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="搜索资源..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9"
            />
          </div>
          <div className="flex gap-2">
            {(["all", "novel", "audio", "comic"] as const).map((type) => (
              <Button
                key={type}
                variant={filter === type ? "default" : "outline"}
                size="sm"
                onClick={() => setFilter(type)}
              >
                {filterLabels[type]}
              </Button>
            ))}
            {selectedIds.size > 0 && (
              <Button
                variant="destructive"
                size="sm"
                onClick={() => setBatchDeleteDialogOpen(true)}
              >
                <Trash2 className="h-4 w-4 mr-2" />
                批量删除 ({selectedIds.size})
              </Button>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm text-muted-foreground px-1">
          小说和音频默认免费；可在此直接修改标题与链接，并保存到数据库。
        </p>
        <div className="rounded-lg border border-border overflow-hidden px-1">
          <Table>
            <TableHeader>
              <TableRow className="bg-muted/50">
                <TableHead className="w-12">
                  <Checkbox
                    checked={selectedIds.size === filteredResources.length && filteredResources.length > 0}
                    onCheckedChange={handleSelectAll}
                  />
                </TableHead>
                <TableHead className="w-1/4">标题</TableHead>
                <TableHead className="w-1/4">Telegram 链接</TableHead>
                <TableHead>类型</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>创建日期</TableHead>
                <TableHead className="w-64 text-right">操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredResources.map((resource) => {
                const config = typeConfig[resource.type]
                const Icon = config.icon
                const entry = editMap[resource.id]
                return (
                  <TableRow key={resource.id}>
                    <TableCell>
                      <Checkbox
                        checked={selectedIds.has(resource.id)}
                        onCheckedChange={(checked) =>
                          handleSelectOne(resource.id, checked as boolean)
                        }
                      />
                    </TableCell>
                    <TableCell className="font-medium">
                      <Input
                        value={entry?.title ?? resource.title}
                        onChange={(e) => handleFieldChange(resource.id, "title", e.target.value)}
                      />
                    </TableCell>
                    <TableCell>
                      <Input
                        value={entry?.link ?? resource.link}
                        onChange={(e) => handleFieldChange(resource.id, "link", e.target.value)}
                      />
                    </TableCell>
                    <TableCell>
                      <Badge variant="secondary" className={config.className}>
                        <Icon className="h-3 w-3 mr-1" />
                        {config.label}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge className={resource.isVip ? "bg-warning text-warning-foreground" : "bg-muted text-muted-foreground"}>
                        {resource.isVip ? (
                          <>
                          <Crown className="h-3 w-3 mr-1" />
                            会员
                          </>
                        ) : (
                          "非会员"
                        )}
                        </Badge>
                    </TableCell>
                    <TableCell className="text-muted-foreground text-sm">{resource.createdAt}</TableCell>
                    <TableCell className="text-right">
                      <div className="flex flex-wrap justify-end gap-2">
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => window.open(resource.link, "_blank")}
                        >
                          <ExternalLink className="h-4 w-4" />
                        </Button>
                        <Button variant="secondary" size="icon" onClick={() => handleCopyDeepLink(resource)}>
                          <Copy className="h-4 w-4" />
                        </Button>
                        {resource.type === "comic" && (
                          <Button
                            variant="outline"
                            size="icon"
                            onClick={() => {
                              setSelectedComicId(resource.id)
                              setComicFilesManagerOpen(true)
                            }}
                            title="管理图片顺序"
                          >
                            <List className="h-4 w-4" />
                          </Button>
                        )}
                        <Button
                          size="icon"
                          onClick={() => handleRowSave(resource)}
                          disabled={!entry?.dirty || entry?.saving}
                        >
                          <Save className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="destructive"
                          size="icon"
                          onClick={() => {
                            setDeletingId(resource.id)
                            setDeleteDialogOpen(true)
                          }}
                        >
                          <Trash2 className="h-4 w-4" />
                          </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                )
              })}
              {loading && (
                <TableRow>
                  <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                    正在加载数据...
                  </TableCell>
                </TableRow>
              )}
              {!loading && filteredResources.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                    未找到资源
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
        {totalCount > 0 && totalCount > pageSize && (
          <div className="mt-4 flex justify-center">
            <Pagination>
              <PaginationContent>
                <PaginationItem>
                  <PaginationPrevious
                    href="#"
                    onClick={(e) => {
                      e.preventDefault()
                      if (page > 1) setPage(page - 1)
                    }}
                    className={page === 1 ? "pointer-events-none opacity-50" : ""}
                  />
                </PaginationItem>
                {Array.from({ length: Math.ceil(totalCount / pageSize) }, (_, i) => i + 1)
                  .filter((p) => {
                    // 只显示当前页附近的页码
                    return p === 1 || p === Math.ceil(totalCount / pageSize) || Math.abs(p - page) <= 2
                  })
                  .map((p, idx, arr) => {
                    // 如果当前页码和下一个页码之间有间隔，显示省略号
                    const prev = arr[idx - 1]
                    const showEllipsis = prev && p - prev > 1
                    return (
                      <React.Fragment key={p}>
                        {showEllipsis && (
                          <PaginationItem>
                            <span className="px-2">...</span>
                          </PaginationItem>
                        )}
                        <PaginationItem>
                          <PaginationLink
                            href="#"
                            onClick={(e) => {
                              e.preventDefault()
                              setPage(p)
                            }}
                            isActive={p === page}
                          >
                            {p}
                          </PaginationLink>
                        </PaginationItem>
                      </React.Fragment>
                    )
                  })}
                <PaginationItem>
                  <PaginationNext
                    href="#"
                    onClick={(e) => {
                      e.preventDefault()
                      if (page < Math.ceil(totalCount / pageSize)) setPage(page + 1)
                    }}
                    className={page >= Math.ceil(totalCount / pageSize) ? "pointer-events-none opacity-50" : ""}
                  />
                </PaginationItem>
              </PaginationContent>
            </Pagination>
          </div>
        )}
      </CardContent>
    </Card>

      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>确认删除</DialogTitle>
            <DialogDescription>
              确定要删除这个资源吗？此操作不可恢复。
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => {
              setDeleteDialogOpen(false)
              setDeletingId(null)
            }}>
              取消
            </Button>
            <Button
              variant="destructive"
              onClick={() => {
                if (deletingId) {
                  removeResource(deletingId)
                  setDeleteDialogOpen(false)
                  setDeletingId(null)
                }
              }}
            >
              删除
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={batchDeleteDialogOpen} onOpenChange={setBatchDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>确认批量删除</DialogTitle>
            <DialogDescription>
              确定要删除选中的 {selectedIds.size} 个资源吗？此操作不可恢复。
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setBatchDeleteDialogOpen(false)}>
              取消
            </Button>
            <Button variant="destructive" onClick={handleBatchDelete}>
              删除
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {selectedComicId && (
        <ComicFilesManager
          resourceId={selectedComicId}
          open={comicFilesManagerOpen}
          onClose={() => {
            setComicFilesManagerOpen(false)
            setSelectedComicId(null)
          }}
        />
      )}
    </>
  )
}
