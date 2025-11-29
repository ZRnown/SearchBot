"use client"

import type React from "react"

import { useCallback, useState, useEffect } from "react"
import { useDropzone } from "react-dropzone"
import { Upload, X, GripVertical } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Progress } from "@/components/ui/progress"
import { cn } from "@/lib/utils"

interface UploadDropzoneProps {
  images: File[]
  onImagesChange: (images: File[]) => void
  maxImages?: number
}

export function UploadDropzone({ images, onImagesChange, maxImages = 200 }: UploadDropzoneProps) {
  const [uploadProgress, setUploadProgress] = useState(0)
  const [draggedIndex, setDraggedIndex] = useState<number | null>(null)
  const [dragOverIndex, setDragOverIndex] = useState<number | null>(null)
  const [previewUrls, setPreviewUrls] = useState<string[]>([])

  useEffect(() => {
    const urls = images.map((file) => URL.createObjectURL(file))
    setPreviewUrls(urls)

    return () => {
      urls.forEach((url) => URL.revokeObjectURL(url))
    }
  }, [images])

  const onDrop = useCallback(
    (acceptedFiles: File[]) => {
      const newImages = [...images, ...acceptedFiles].slice(0, maxImages)
      onImagesChange(newImages)

      setUploadProgress(0)
      const interval = setInterval(() => {
        setUploadProgress((prev) => {
          if (prev >= 100) {
            clearInterval(interval)
            return 100
          }
          return prev + 10
        })
      }, 100)
    },
    [images, onImagesChange, maxImages],
  )

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "image/*": [".png", ".jpg", ".jpeg", ".webp"] },
    maxFiles: maxImages - images.length,
  })

  const removeImage = (index: number) => {
    onImagesChange(images.filter((_, i) => i !== index))
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
      const newImages = [...images]
      const [removed] = newImages.splice(draggedIndex, 1)
      newImages.splice(dragOverIndex, 0, removed)
      onImagesChange(newImages)
    }
    setDraggedIndex(null)
    setDragOverIndex(null)
  }

  return (
    <div className="space-y-4">
      <div
        {...getRootProps()}
        className={cn(
          "border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors",
          isDragActive ? "border-primary bg-primary/5" : "border-border hover:border-primary/50",
        )}
      >
        <input {...getInputProps()} />
        <Upload className="h-10 w-10 mx-auto text-muted-foreground mb-3" />
        <p className="text-sm text-muted-foreground">{isDragActive ? "将图片放在这里..." : "拖放图片，或点击选择"}</p>
        <p className="text-xs text-muted-foreground mt-1">
          {images.length} / {maxImages} 张图片
        </p>
      </div>

      {uploadProgress > 0 && uploadProgress < 100 && (
        <div className="space-y-2">
          <Progress value={uploadProgress} />
          <p className="text-xs text-muted-foreground text-center">上传中... {uploadProgress}%</p>
        </div>
      )}

      {images.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs text-muted-foreground">拖动图片可调整顺序</p>
          <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 gap-3 max-h-80 overflow-y-auto p-2 bg-muted rounded-lg">
            {images.map((file, index) => (
              <div
                key={index}
                draggable
                onDragStart={(e) => handleDragStart(e, index)}
                onDragOver={(e) => handleDragOver(e, index)}
                onDragEnd={handleDragEnd}
                className={cn(
                  "relative group aspect-[3/4] cursor-move transition-all rounded-lg overflow-hidden border-2 border-transparent",
                  draggedIndex === index && "opacity-50 scale-95",
                  dragOverIndex === index && draggedIndex !== index && "border-primary",
                )}
              >
                <img
                  src={previewUrls[index] || "/placeholder.svg"}
                  alt={`第 ${index + 1} 页`}
                  className="w-full h-full object-cover"
                />
                {/* 拖动手柄 */}
                <div className="absolute top-1 left-1 bg-black/50 rounded p-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                  <GripVertical className="h-4 w-4 text-white" />
                </div>
                {/* 删除按钮 */}
                <Button
                  variant="destructive"
                  size="icon"
                  className="absolute top-1 right-1 h-5 w-5 opacity-0 group-hover:opacity-100 transition-opacity"
                  onClick={() => removeImage(index)}
                >
                  <X className="h-3 w-3" />
                </Button>
                {/* 页码标签 */}
                <span className="absolute bottom-0 left-0 right-0 text-xs text-center bg-primary/90 text-primary-foreground font-medium py-1">
                  第 {index + 1} 页
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
