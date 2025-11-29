import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Book, Headphones, Heart, Crown } from "lucide-react"

interface PreviewCardProps {
  title: string
  type: "novel" | "audio" | "comic"
  isVip?: boolean
  telegramLink?: string
}

const typeConfig = {
  novel: { icon: Book, label: "小说", color: "bg-primary" },
  audio: { icon: Headphones, label: "音频", color: "bg-chart-2" },
  comic: { icon: Heart, label: "漫画", color: "bg-chart-5" },
}

export function PreviewCard({ title, type, isVip, telegramLink }: PreviewCardProps) {
  const config = typeConfig[type]
  const Icon = config.icon

  return (
    <Card className="overflow-hidden border-border">
      <div className={`${config.color} px-4 py-2 flex items-center gap-2`}>
        <Icon className="h-4 w-4 text-primary-foreground" />
        <span className="text-sm font-medium text-primary-foreground">{config.label}</span>
        {isVip && (
          <Badge variant="secondary" className="ml-auto bg-warning text-warning-foreground">
            <Crown className="h-3 w-3 mr-1" />
            VIP
          </Badge>
        )}
      </div>
      <CardContent className="p-4 space-y-3">
        <h3 className="font-semibold text-card-foreground text-balance">{title || "未命名资源"}</h3>
        {telegramLink && <p className="text-sm text-muted-foreground break-all">{telegramLink}</p>}
        <div className="pt-2 border-t border-border">
          <span className="text-xs text-muted-foreground">Telegram 消息预览</span>
        </div>
      </CardContent>
    </Card>
  )
}
