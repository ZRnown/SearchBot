"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Button } from "@/components/ui/button"
import { Switch } from "@/components/ui/switch"
import { Badge } from "@/components/ui/badge"
import { UploadDropzone } from "./upload-dropzone"
import { Heart, ChevronRight, ChevronLeft, Check, Link2, Copy, Archive, Upload, X, GripVertical, Save, List } from "lucide-react"
import { uploadComic, uploadComicArchive, batchUploadComicArchives, updateResource } from "@/lib/api"
import { ComicFilesManager } from "./comic-files-manager"
import { useToast } from "@/components/ui/use-toast"
import JSZip from "jszip"

type Step = 1 | 2 | 3
type UploadMode = "images" | "archive" | "batch-archive"

export function ComicUploadWizard({ className = "" }: { className?: string } = {}) {
  const [step, setStep] = useState<Step>(1)
  const [uploadMode, setUploadMode] = useState<UploadMode>("images")
  const [title, setTitle] = useState("")
  const [isVip, setIsVip] = useState(false)
  const [images, setImages] = useState<File[]>([])
  const [archive, setArchive] = useState<File | null>(null)
  const [archives, setArchives] = useState<File[]>([])
  const [archiveImages, setArchiveImages] = useState<Array<{ name: string; url: string; file: File }>>([])
  const [archiveImagesLoading, setArchiveImagesLoading] = useState(false)
  const [draggedImageIndex, setDraggedImageIndex] = useState<number | null>(null)
  const [dragOverImageIndex, setDragOverImageIndex] = useState<number | null>(null)
  const [uploadedPages, setUploadedPages] = useState<number>(0)
  const [deepLink, setDeepLink] = useState("")
  const [previewLink, setPreviewLink] = useState("")
  const [uploadResults, setUploadResults] = useState<Array<{ id: string; title: string; originalFileName: string; order: number; pages: number; deepLink: string; previewLink: string }>>([])
  const [editingTitles, setEditingTitles] = useState<Record<string, string>>({})
  const [isUploading, setIsUploading] = useState(false)
  const [comicFilesManagerOpen, setComicFilesManagerOpen] = useState(false)
  const [selectedComicId, setSelectedComicId] = useState<string>("")
  const { toast } = useToast()

  const canProceedStep1 = uploadMode === "batch-archive" ? archives.length > 0 : title.trim().length > 0
  const canProceedStep2 = 
    uploadMode === "images" ? images.length > 0 : 
    uploadMode === "archive" ? archive !== null : 
    archives.length > 0

  const handleFinish = async () => {
    if (!canProceedStep1 || !canProceedStep2 || isUploading) return
    try {
      setIsUploading(true)
      if (uploadMode === "batch-archive" && archives.length > 0) {
        const results = await batchUploadComicArchives({
          archives,
          isVip,
          previewCount: 5,
        })
        const resultsWithTitles = results.map((r, idx) => ({
          id: r.id,
          title: archives[idx]?.name.replace(/\.(zip|rar)$/i, "") || `漫画 ${idx + 1}`,
          originalFileName: archives[idx]?.name || `漫画 ${idx + 1}`,
          order: idx + 1,
          pages: r.pages,
          deepLink: r.deepLink,
          previewLink: r.previewLink,
        }))
        setUploadResults(resultsWithTitles)
        // 初始化编辑状态
        const initialTitles: Record<string, string> = {}
        resultsWithTitles.forEach(r => {
          initialTitles[r.id] = r.title
        })
        setEditingTitles(initialTitles)
        setStep(3)
        toast({
          title: "批量上传成功",
          description: `成功上传 ${results.length} 个压缩包`,
        })
      } else {
        let result
        if (uploadMode === "archive" && archive) {
          result = await uploadComicArchive({
            title: title.trim(),
            isVip,
            archive,
            previewCount: 5,
          })
        } else {
          result = await uploadComic({
            title: title.trim(),
            isVip,
            files: images,
          })
        }
        setDeepLink(result.deepLink)
        setPreviewLink(result.previewLink)
        setUploadedPages(result.pages)
    setStep(3)
        toast({
          title: "上传成功",
          description: `共 ${result.pages} 张图片，链接已就绪`,
        })
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "上传失败"
      toast({
        title: "上传失败",
        description: message,
        variant: "destructive",
      })
    } finally {
      setIsUploading(false)
    }
  }

  const copyLink = () => {
    navigator.clipboard.writeText(deepLink)
  }

  const extractImagesFromZip = async (file: File): Promise<Array<{ name: string; url: string; file: File }>> => {
    try {
      const zip = await JSZip.loadAsync(file)
      const imageFiles: Array<{ name: string; url: string; file: File }> = []
      const imageExtensions = ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp']
      
      for (const [filename, zipEntry] of Object.entries(zip.files)) {
        if (zipEntry.dir) continue
        const ext = filename.toLowerCase().substring(filename.lastIndexOf('.'))
        if (imageExtensions.includes(ext)) {
          const blob = await zipEntry.async('blob')
          const file = new File([blob], filename, { type: `image/${ext.slice(1)}` })
          const url = URL.createObjectURL(blob)
          imageFiles.push({ name: filename, url, file })
        }
      }
      
      // 按文件名排序
      imageFiles.sort((a, b) => a.name.localeCompare(b.name))
      return imageFiles
    } catch (error) {
      console.error('解压失败:', error)
      throw new Error('无法解压压缩包，请确保是有效的 zip 文件')
    }
  }

  const handleArchiveSelect = async (file: File) => {
    if (file.name.toLowerCase().endsWith('.zip')) {
      try {
        setArchiveImagesLoading(true)
        const images = await extractImagesFromZip(file)
        setArchiveImages(images)
        setArchive(file)
      } catch (error) {
        const message = error instanceof Error ? error.message : "解压失败"
        toast({
          title: "解压失败",
          description: message,
          variant: "destructive",
        })
      } finally {
        setArchiveImagesLoading(false)
      }
    } else {
      // RAR 文件无法在前端解压，只设置文件
      setArchive(file)
      setArchiveImages([])
    }
  }

  const handleImageDragStart = (e: React.DragEvent, index: number) => {
    setDraggedImageIndex(index)
    e.dataTransfer.effectAllowed = "move"
  }

  const handleImageDragOver = (e: React.DragEvent, index: number) => {
    e.preventDefault()
    setDragOverImageIndex(index)
  }

  const handleImageDragEnd = () => {
    if (draggedImageIndex !== null && dragOverImageIndex !== null && draggedImageIndex !== dragOverImageIndex) {
      const newImages = [...archiveImages]
      const [removed] = newImages.splice(draggedImageIndex, 1)
      newImages.splice(dragOverImageIndex, 0, removed)
      setArchiveImages(newImages)
    }
    setDraggedImageIndex(null)
    setDragOverImageIndex(null)
  }

  const resetWizard = () => {
    setStep(1)
    setUploadMode("images")
    setTitle("")
    setIsVip(false)
    setImages([])
    setArchive(null)
    setArchives([])
    setArchiveImages([])
    setUploadedPages(0)
    setDeepLink("")
    setPreviewLink("")
    setUploadResults([])
    // 清理 URL
    archiveImages.forEach(img => URL.revokeObjectURL(img.url))
  }

  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-card-foreground">
          <Heart className="h-5 w-5 text-chart-5" />
          上传漫画
        </CardTitle>
        <div className="flex items-center gap-2 mt-4">
          {[1, 2, 3].map((s) => (
            <div key={s} className="flex items-center">
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium transition-colors ${step >= s ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"}`}
              >
                {step > s ? <Check className="h-4 w-4" /> : s}
              </div>
              {s < 3 && <div className={`w-12 h-0.5 mx-1 ${step > s ? "bg-primary" : "bg-muted"}`}></div>}
            </div>
          ))}
        </div>
      </CardHeader>
      <CardContent>
        {step === 1 && (
          <div className="space-y-5">
            {uploadMode !== "batch-archive" && (
            <div className="space-y-2">
              <Label htmlFor="comic-title">漫画标题</Label>
              <Input
                id="comic-title"
                placeholder="输入漫画标题..."
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
            </div>
            )}

            <div className="space-y-2">
              <Label>上传方式</Label>
              <div className="grid grid-cols-3 gap-2">
                <Button
                  type="button"
                  variant={uploadMode === "images" ? "default" : "outline"}
                  className="flex-1"
                  onClick={() => {
                    setUploadMode("images")
                    setArchive(null)
                    setArchives([])
                  }}
                >
                  <Upload className="h-4 w-4 mr-2" />
                  上传图片
                </Button>
                <Button
                  type="button"
                  variant={uploadMode === "archive" ? "default" : "outline"}
                  className="flex-1"
                  onClick={() => {
                    setUploadMode("archive")
                    setImages([])
                    setArchives([])
                  }}
                >
                  <Archive className="h-4 w-4 mr-2" />
                  单个压缩包
                </Button>
                <Button
                  type="button"
                  variant={uploadMode === "batch-archive" ? "default" : "outline"}
                  className="flex-1"
                  onClick={() => {
                    setUploadMode("batch-archive")
                    setImages([])
                    setArchive(null)
                  }}
                >
                  <Archive className="h-4 w-4 mr-2" />
                  批量压缩包
                </Button>
              </div>
              <p className="text-xs text-muted-foreground">
                {uploadMode === "archive"
                  ? "支持 zip/rar 格式，将自动解压并发送到存储频道和预览频道"
                  : uploadMode === "batch-archive"
                  ? "批量上传多个压缩包，每个压缩包将自动创建独立的漫画资源，默认使用压缩包名称作为标题"
                  : "逐个上传图片文件"}
              </p>
            </div>

            {uploadMode === "batch-archive" && (
              <div className="space-y-4">
                <Label>批量上传压缩包 (zip/rar)</Label>
                <div
                  className="border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors hover:border-primary/50"
                  onClick={() => {
                    const input = document.createElement("input")
                    input.type = "file"
                    input.accept = ".zip,.rar"
                    input.multiple = true
                    input.onchange = (e) => {
                      const files = Array.from((e.target as HTMLInputElement).files || [])
                      if (files.length > 0) {
                        setArchives([...archives, ...files])
                      }
                    }
                    input.click()
                  }}
                >
                  <Archive className="h-10 w-10 mx-auto text-muted-foreground mb-3" />
                  <p className="text-sm text-muted-foreground">
                    点击选择多个压缩包文件
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">
                    支持 zip 和 rar 格式，每个压缩包将自动创建独立的漫画资源
                  </p>
                </div>
                {archives.length > 0 && (
                  <div className="space-y-2">
                    <p className="text-sm font-medium">已选择 {archives.length} 个压缩包：</p>
                    <div className="space-y-2 max-h-60 overflow-y-auto">
                      {archives.map((file, idx) => (
                        <div key={idx} className="p-3 bg-muted rounded-lg flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <Archive className="h-4 w-4" />
                            <span className="text-sm">{file.name}</span>
                            <span className="text-xs text-muted-foreground">
                              ({(file.size / 1024 / 1024).toFixed(2)} MB)
                            </span>
                          </div>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setArchives(archives.filter((_, i) => i !== idx))}
                          >
                            <X className="h-4 w-4" />
                          </Button>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            <div className="flex items-center justify-between p-3 rounded-lg bg-muted">
              <div className="space-y-0.5">
                <Label htmlFor="comic-vip" className="cursor-pointer">
                  仅限 VIP
                </Label>
                <p className="text-xs text-muted-foreground">限制为 VIP 会员访问</p>
              </div>
              <Switch id="comic-vip" checked={isVip} onCheckedChange={setIsVip} />
            </div>

            <Button
              className="w-full"
              onClick={() => setStep(2)}
              disabled={!canProceedStep1}
            >
              下一步：{uploadMode === "batch-archive" ? "确认上传" : uploadMode === "archive" ? "上传压缩包" : "上传图片"}
              <ChevronRight className="h-4 w-4 ml-2" />
            </Button>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-5">
            {uploadMode === "images" ? (
            <UploadDropzone images={images} onImagesChange={setImages} maxImages={200} />
            ) : uploadMode === "batch-archive" ? (
              <div className="space-y-4">
                <div className="p-4 bg-muted rounded-lg">
                  <p className="text-sm font-medium mb-2">准备上传 {archives.length} 个压缩包：</p>
                  <div className="space-y-2 max-h-60 overflow-y-auto">
                    {archives.map((file, idx) => (
                      <div key={idx} className="p-2 bg-background rounded flex items-center gap-2">
                        <Archive className="h-4 w-4 shrink-0" />
                        <span className="text-sm flex-1">{file.name}</span>
                        <span className="text-xs text-muted-foreground shrink-0">
                          ({(file.size / 1024 / 1024).toFixed(2)} MB)
                        </span>
                      </div>
                    ))}
                  </div>
                  <p className="text-xs text-muted-foreground mt-3">
                    每个压缩包将自动创建独立的漫画资源，默认使用压缩包名称（去掉扩展名）作为漫画标题
                  </p>
                </div>
              </div>
            ) : (
              <div className="space-y-4">
                <Label>上传压缩包 (zip/rar)</Label>
                <div
                  className="border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors hover:border-primary/50"
                  onClick={() => {
                    const input = document.createElement("input")
                    input.type = "file"
                    input.accept = ".zip,.rar"
                    input.onchange = (e) => {
                      const file = (e.target as HTMLInputElement).files?.[0]
                      if (file) {
                        handleArchiveSelect(file)
                      }
                    }
                    input.click()
                  }}
                >
                  <Archive className="h-10 w-10 mx-auto text-muted-foreground mb-3" />
                  <p className="text-sm text-muted-foreground">
                    {archive ? archive.name : "点击选择压缩包文件"}
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">
                    支持 zip 和 rar 格式，将自动解压并上传所有图片
                  </p>
                </div>
                {archiveImagesLoading && (
                  <div className="text-center py-4 text-muted-foreground">正在解压并加载图片...</div>
                )}
                {archive && !archiveImagesLoading && (
                  <>
                    <div className="p-3 bg-muted rounded-lg flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Archive className="h-4 w-4" />
                        <span className="text-sm">{archive.name}</span>
                        <span className="text-xs text-muted-foreground">
                          ({(archive.size / 1024 / 1024).toFixed(2)} MB)
                        </span>
                        {archiveImages.length > 0 && (
                          <span className="text-xs text-muted-foreground">
                            • {archiveImages.length} 张图片
                          </span>
                        )}
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          archiveImages.forEach(img => URL.revokeObjectURL(img.url))
                          setArchive(null)
                          setArchiveImages([])
                        }}
                      >
                        <X className="h-4 w-4" />
                      </Button>
                    </div>
                    {archiveImages.length > 0 && (
                      <div className="space-y-4">
                        <p className="text-base font-medium">图片预览（拖动可调整顺序）：</p>
                        <div className="grid grid-cols-4 sm:grid-cols-5 md:grid-cols-6 lg:grid-cols-8 xl:grid-cols-10 2xl:grid-cols-12 gap-4 max-h-96 overflow-y-auto p-2 bg-muted rounded-lg">
                          {archiveImages.map((img, idx) => (
                            <div
                              key={idx}
                              draggable
                              onDragStart={(e) => handleImageDragStart(e, idx)}
                              onDragOver={(e) => handleImageDragOver(e, idx)}
                              onDragEnd={handleImageDragEnd}
                              className={cn(
                                "relative group aspect-[3/4] border-3 rounded-xl overflow-hidden cursor-move transition-all shadow-lg hover:shadow-xl",
                                draggedImageIndex === idx && "opacity-50 scale-95",
                                dragOverImageIndex === idx && draggedImageIndex !== idx && "border-primary ring-4 ring-primary ring-opacity-50",
                              )}
                            >
                              <div className="absolute top-2 left-2 z-10 bg-black/70 rounded-md p-1.5 opacity-0 group-hover:opacity-100 transition-opacity">
                                <GripVertical className="h-5 w-5 text-white" />
                              </div>
                              <img
                                src={img.url}
                                alt={img.name}
                                className="w-full h-full object-cover"
                              />
                              <div className="absolute bottom-0 left-0 right-0 bg-black/80 text-white text-sm font-semibold text-center py-2">
                                {idx + 1}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </>
                )}
              </div>
            )}

            <div className="flex gap-3">
              <Button variant="outline" onClick={() => setStep(1)} className="flex-1">
                <ChevronLeft className="h-4 w-4 mr-2" />
                返回
              </Button>
              <Button onClick={handleFinish} disabled={!canProceedStep2 || isUploading} className="flex-1">
                {isUploading ? "上传中..." : "完成上传"}
                <ChevronRight className="h-4 w-4 ml-2" />
              </Button>
            </div>
          </div>
        )}

        {step === 3 && (
          <div className="space-y-5 text-center">
            <div className="w-16 h-16 rounded-full bg-success/10 flex items-center justify-center mx-auto">
              <Check className="h-8 w-8 text-success" />
            </div>

            {uploadMode === "batch-archive" ? (
              <>
                <div>
                  <h3 className="font-semibold text-lg text-card-foreground">批量上传成功</h3>
                  <p className="text-sm text-muted-foreground mt-1">
                    成功上传 {uploadResults.length} 个压缩包
                    {isVip && " • 仅限 VIP"}
                  </p>
                </div>

                <div className="space-y-3 max-h-96 overflow-y-auto text-left">
                  {uploadResults.map((result) => (
                    <div key={result.id} className="p-4 bg-muted rounded-lg space-y-3">
                      <div className="flex items-center justify-between gap-3">
                        <div className="flex-1 space-y-2">
                          <div className="flex items-center gap-2">
                            <Badge variant="outline" className="shrink-0">
                              第 {result.order} 个
                            </Badge>
                            <Input
                              value={editingTitles[result.id] ?? result.title}
                              onChange={(e) => {
                                setEditingTitles({
                                  ...editingTitles,
                                  [result.id]: e.target.value,
                                })
                              }}
                              className="font-medium flex-1"
                              placeholder="漫画标题"
                            />
                            <Button
                              size="sm"
                              onClick={async () => {
                                try {
                                  const newTitle = editingTitles[result.id]?.trim()
                                  if (!newTitle) {
                                    toast({
                                      title: "标题不能为空",
                                      variant: "destructive",
                                    })
                                    return
                                  }
                                  await updateResource(result.id, { title: newTitle })
                                  setUploadResults(uploadResults.map(r =>
                                    r.id === result.id ? { ...r, title: newTitle } : r
                                  ))
                                  toast({
                                    title: "标题已更新",
                                  })
                                } catch (error) {
                                  const message = error instanceof Error ? error.message : "更新失败"
                                  toast({
                                    title: "更新失败",
                                    description: message,
                                    variant: "destructive",
                                  })
                                }
                              }}
                            >
                              <Save className="h-3 w-3 mr-1" />
                              保存
                            </Button>
                          </div>
                          <div className="flex items-center gap-2 text-xs text-muted-foreground">
                            <span>原文件名：{result.originalFileName}</span>
                            <span>•</span>
                            <span>{result.pages} 张图片</span>
                          </div>
                        </div>
                        <Badge className="bg-success text-success-foreground shrink-0">已上传</Badge>
                      </div>
                      <div className="space-y-2">
                        <div className="flex gap-2">
                          <div className="flex-1 p-2 bg-background rounded text-xs">
                            <p className="text-muted-foreground mb-1">深度链接</p>
                            <p className="font-mono truncate">{result.deepLink}</p>
                          </div>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => {
                              navigator.clipboard.writeText(result.deepLink)
                              toast({ title: "已复制深度链接" })
                            }}
                          >
                            <Copy className="h-3 w-3" />
                          </Button>
                        </div>
                        <div className="flex gap-2">
                          <div className="flex-1 p-2 bg-background rounded text-xs">
                            <p className="text-muted-foreground mb-1">预览频道链接</p>
                            <p className="font-mono truncate">{result.previewLink}</p>
                          </div>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => {
                              navigator.clipboard.writeText(result.previewLink)
                              toast({ title: "已复制预览链接" })
                            }}
                          >
                            <Copy className="h-3 w-3" />
                          </Button>
                        </div>
                      </div>
                      <div className="flex justify-end">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            setSelectedComicId(result.id)
                            setComicFilesManagerOpen(true)
                          }}
                        >
                          <List className="h-3 w-3 mr-1" />
                          管理图片顺序
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <>
            <div>
              <h3 className="font-semibold text-lg text-card-foreground">{title}</h3>
              <p className="text-sm text-muted-foreground mt-1">
                    已上传 {uploadedPages} 张图片
                {isVip && " • 仅限 VIP"}
              </p>
            </div>

            <div className="p-4 bg-muted rounded-lg space-y-2">
              <Label className="text-xs text-muted-foreground">深度链接</Label>
              <div className="flex gap-2">
                <Input value={deepLink} readOnly className="font-mono text-xs" />
                <Button variant="outline" size="icon" onClick={copyLink}>
                  <Copy className="h-4 w-4" />
                </Button>
              </div>
            </div>

                <div className="p-4 bg-muted rounded-lg space-y-2">
                  <Label className="text-xs text-muted-foreground">当前跳转链接</Label>
                  <Input value={previewLink} readOnly className="font-mono text-xs" />
                </div>

            <Badge className="bg-success text-success-foreground">
              <Link2 className="h-3 w-3 mr-1" />
              已准备好分享
            </Badge>
              </>
            )}

            <Button variant="outline" onClick={resetWizard} className="w-full bg-transparent">
              上传另一部漫画
            </Button>
          </div>
        )}
      </CardContent>
      {selectedComicId && (
        <ComicFilesManager
          resourceId={selectedComicId}
          open={comicFilesManagerOpen}
          onClose={() => {
            setComicFilesManagerOpen(false)
            setSelectedComicId("")
          }}
        />
      )}
    </Card>
  )
}

function cn(...classes: (string | boolean | undefined)[]) {
  return classes.filter(Boolean).join(" ")
}
