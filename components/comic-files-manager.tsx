"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { GripVertical, Save, X } from "lucide-react"
import { getComicFiles, updateComicFilesOrder, getComicFileUrl, type ComicFilesData } from "@/lib/api"
import { useToast } from "@/components/ui/use-toast"
import { cn } from "@/lib/utils"

interface ComicFilesManagerProps {
  resourceId: string
  open: boolean
  onClose: () => void
}

export function ComicFilesManager({ resourceId, open, onClose }: ComicFilesManagerProps) {
  const [data, setData] = useState<ComicFilesData | null>(null)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [files, setFiles] = useState<Array<{ id: number; fileId: string; order: number }>>([])
  const [draggedIndex, setDraggedIndex] = useState<number | null>(null)
  const [dragOverIndex, setDragOverIndex] = useState<number | null>(null)
  const [imageUrls, setImageUrls] = useState<Record<string, string>>({})
  const { toast } = useToast()

  useEffect(() => {
    if (open && resourceId) {
      loadFiles()
    }
  }, [open, resourceId])

  useEffect(() => {
    if (open && files.length > 0) {
      // 加载所有图片 URL
      const loadUrls = async () => {
        const urls: Record<string, string> = {}
        for (const file of files) {
          try {
            const url = await getComicFileUrl(file.fileId)
            urls[file.id] = url
          } catch (error) {
            console.error(`Failed to load image for file ${file.id}:`, error)
          }
        }
        setImageUrls(urls)
      }
      loadUrls()
    }
  }, [open, files])

  const loadFiles = async () => {
    try {
      setLoading(true)
      const result = await getComicFiles(resourceId)
      setData(result)
      setFiles([...result.files].sort((a, b) => a.order - b.order))
    } catch (error) {
      const message = error instanceof Error ? error.message : "加载失败"
      toast({
        title: "加载失败",
        description: message,
        variant: "destructive",
      })
    } finally {
      setLoading(false)
    }
  }

  const handleDragStart = (e: React.DragEvent, index: number) => {
    setDraggedIndex(index)
    e.dataTransfer.effectAllowed = "move"
  }

  const handleDragOver = (e: React.DragEvent, index: number) => {
    e.preventDefault()
    setDragOverIndex(index)
  }

  const handleDragEnd = () => {
    if (draggedIndex !== null && dragOverIndex !== null && draggedIndex !== dragOverIndex) {
      const newFiles = [...files]
      const [removed] = newFiles.splice(draggedIndex, 1)
      newFiles.splice(dragOverIndex, 0, removed)
      // 更新顺序
      const updatedFiles = newFiles.map((file, idx) => ({
        ...file,
        order: idx + 1,
      }))
      setFiles(updatedFiles)
    }
    setDraggedIndex(null)
    setDragOverIndex(null)
  }

  const handleSave = async () => {
    try {
      setSaving(true)
      const fileOrders = files.map((file) => ({
        id: file.id,
        order: file.order,
      }))
      await updateComicFilesOrder(resourceId, fileOrders)
      toast({
        title: "保存成功",
        description: "图片顺序已更新",
      })
      await loadFiles() // 重新加载以确认
    } catch (error) {
      const message = error instanceof Error ? error.message : "保存失败"
      toast({
        title: "保存失败",
        description: message,
        variant: "destructive",
      })
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="!max-w-[100vw] !w-[100vw] !max-h-[100vh] !h-[100vh] overflow-hidden flex flex-col p-4 !m-0 !rounded-none">
        <DialogHeader className="flex-shrink-0 pb-3">
          <DialogTitle className="text-2xl font-bold">管理图片顺序 - {data?.title}</DialogTitle>
          <DialogDescription className="text-base">
            拖动图片可调整顺序，调整后点击保存按钮
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto">
          {loading ? (
            <div className="py-8 text-center text-muted-foreground">加载中...</div>
          ) : files.length === 0 ? (
            <div className="py-8 text-center text-muted-foreground">暂无图片</div>
          ) : (
            <div className="space-y-4 py-4">
              <p className="text-base font-medium">
                共 {files.length} 张图片，当前按顺序排列
              </p>
              <div className="grid grid-cols-4 sm:grid-cols-5 md:grid-cols-6 lg:grid-cols-8 xl:grid-cols-10 2xl:grid-cols-12 gap-4">
                {files.map((file, index) => (
                  <div
                    key={file.id}
                    draggable
                    onDragStart={(e) => handleDragStart(e, index)}
                    onDragOver={(e) => handleDragOver(e, index)}
                    onDragEnd={handleDragEnd}
                  className={cn(
                    "relative group aspect-[3/4] border-3 rounded-xl overflow-hidden cursor-move transition-all shadow-lg hover:shadow-xl",
                    draggedIndex === index && "opacity-50 scale-95",
                    dragOverIndex === index && draggedIndex !== index && "border-primary ring-4 ring-primary ring-opacity-50",
                  )}
                >
                  <div className="absolute top-2 left-2 z-10 bg-black/70 rounded-md p-1.5 opacity-0 group-hover:opacity-100 transition-opacity">
                    <GripVertical className="h-5 w-5 text-white" />
                  </div>
                  <div className="w-full h-full bg-muted flex items-center justify-center">
                    {imageUrls[file.id] ? (
                      <img
                        src={imageUrls[file.id]}
                        alt={`第 ${file.order} 张`}
                        className="w-full h-full object-cover"
                        loading="lazy"
                      />
                    ) : (
                      <div className="text-sm text-muted-foreground text-center p-4">加载中...</div>
                    )}
                  </div>
                  <div className="absolute bottom-0 left-0 right-0 bg-black/80 text-white text-sm font-semibold text-center py-2">
                    第 {file.order} 张
                  </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <DialogFooter className="flex-shrink-0 border-t pt-4 mt-4">
          <Button variant="outline" onClick={onClose}>
            取消
          </Button>
          <Button onClick={handleSave} disabled={saving || loading}>
            {saving ? "保存中..." : "保存顺序"}
            <Save className="h-4 w-4 ml-2" />
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

