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

// VIP 支付设置组件（已迁移到独立页面使用，不再在设置面板中展示）
function VipPaymentSettings() {
  const [vipPlans, setVipPlans] = useState<any[]>([])
  const [paymentConfigs, setPaymentConfigs] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [showPlanForm, setShowPlanForm] = useState(false)
  const [showPaymentForm, setShowPaymentForm] = useState(false)
  const [editingPlan, setEditingPlan] = useState<any>(null)
  const [editingPayment, setEditingPayment] = useState<any>(null)
  const { toast } = useToast()

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      setLoading(true)
      const [plansRes, configsRes] = await Promise.all([
        fetch("/api/vip-plans"),
        fetch("/api/payment-configs"),
      ])
      if (plansRes.ok) {
        const plans = await plansRes.json()
        setVipPlans(plans)
      }
      if (configsRes.ok) {
        const configs = await configsRes.json()
        setPaymentConfigs(configs)
      }
    } catch (error) {
      toast({
        title: "加载失败",
        description: error instanceof Error ? error.message : "请稍后再试",
        variant: "destructive",
      })
    } finally {
      setLoading(false)
    }
  }

  const handleSavePlan = async (plan: any) => {
    try {
      const url = editingPlan ? `/api/vip-plans/${editingPlan.id}` : "/api/vip-plans"
      const method = editingPlan ? "PUT" : "POST"
      const res = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(plan),
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.detail ?? "保存失败")
      }
      toast({ title: "保存成功" })
      setShowPlanForm(false)
      setEditingPlan(null)
      loadData()
    } catch (error) {
      toast({
        title: "保存失败",
        description: error instanceof Error ? error.message : "请稍后再试",
        variant: "destructive",
      })
    }
  }

  const handleDeletePlan = async (id: number) => {
    if (!confirm("确定要删除这个套餐吗？")) return
    try {
      const res = await fetch(`/api/vip-plans/${id}`, { method: "DELETE" })
      if (!res.ok) throw new Error("删除失败")
      toast({ title: "删除成功" })
      loadData()
    } catch (error) {
      toast({
        title: "删除失败",
        description: error instanceof Error ? error.message : "请稍后再试",
        variant: "destructive",
      })
    }
  }

  const handleSavePayment = async (config: any) => {
    try {
      const url = editingPayment ? `/api/payment-configs/${editingPayment.id}` : "/api/payment-configs"
      const method = editingPayment ? "PUT" : "POST"
      const res = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config),
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.detail ?? "保存失败")
      }
      toast({ title: "保存成功" })
      setShowPaymentForm(false)
      setEditingPayment(null)
      loadData()
    } catch (error) {
      toast({
        title: "保存失败",
        description: error instanceof Error ? error.message : "请稍后再试",
        variant: "destructive",
      })
    }
  }

  const handleDeletePayment = async (id: number) => {
    if (!confirm("确定要删除这个支付配置吗？")) return
    try {
      const res = await fetch(`/api/payment-configs/${id}`, { method: "DELETE" })
      if (!res.ok) throw new Error("删除失败")
      toast({ title: "删除成功" })
      loadData()
    } catch (error) {
      toast({
        title: "删除失败",
        description: error instanceof Error ? error.message : "请稍后再试",
        variant: "destructive",
      })
    }
  }

  const wechatConfig = paymentConfigs.find((c) => c.payment_type === "wechat")
  const alipayConfig = paymentConfigs.find((c) => c.payment_type === "alipay")

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-card-foreground">
            💰 VIP 套餐管理
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {loading ? (
            <p className="text-sm text-muted-foreground">加载中...</p>
          ) : (
            <>
              {vipPlans.map((plan) => (
                <div key={plan.id} className="flex items-center justify-between p-3 rounded-lg bg-muted">
                  <div>
                    <p className="font-medium text-sm">{plan.name}</p>
                    <p className="text-xs text-muted-foreground">
                      ¥{plan.price} / {plan.duration_days}天
                      {plan.description && ` - ${plan.description}`}
                    </p>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        setEditingPlan(plan)
                        setShowPlanForm(true)
                      }}
                    >
                      编辑
                    </Button>
                    <Button
                      size="sm"
                      variant="destructive"
                      onClick={() => handleDeletePlan(plan.id)}
                    >
                      删除
                    </Button>
                  </div>
                </div>
              ))}
              <Button onClick={() => setShowPlanForm(true)} className="w-full">
                添加套餐
              </Button>
            </>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-card-foreground">
            💳 支付配置
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {loading ? (
            <p className="text-sm text-muted-foreground">加载中...</p>
          ) : (
            <>
              <div className="space-y-3">
                <div className="p-3 rounded-lg bg-muted">
                  <p className="font-medium text-sm mb-2">微信支付</p>
                  {wechatConfig ? (
                    <div className="space-y-1">
                      {wechatConfig.account_name && (
                        <p className="text-xs text-muted-foreground">收款人：{wechatConfig.account_name}</p>
                      )}
                      {wechatConfig.account_number && (
                        <p className="text-xs text-muted-foreground">账号：{wechatConfig.account_number}</p>
                      )}
                      <div className="flex gap-2 mt-2">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => {
                            setEditingPayment(wechatConfig)
                            setShowPaymentForm(true)
                          }}
                        >
                          编辑
                        </Button>
                        <Button
                          size="sm"
                          variant="destructive"
                          onClick={() => handleDeletePayment(wechatConfig.id)}
                        >
                          删除
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        setEditingPayment({ payment_type: "wechat" })
                        setShowPaymentForm(true)
                      }}
                    >
                      添加微信支付
                    </Button>
                  )}
                </div>

                <div className="p-3 rounded-lg bg-muted">
                  <p className="font-medium text-sm mb-2">支付宝</p>
                  {alipayConfig ? (
                    <div className="space-y-1">
                      {alipayConfig.account_name && (
                        <p className="text-xs text-muted-foreground">收款人：{alipayConfig.account_name}</p>
                      )}
                      {alipayConfig.account_number && (
                        <p className="text-xs text-muted-foreground">账号：{alipayConfig.account_number}</p>
                      )}
                      <div className="flex gap-2 mt-2">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => {
                            setEditingPayment(alipayConfig)
                            setShowPaymentForm(true)
                          }}
                        >
                          编辑
                        </Button>
                        <Button
                          size="sm"
                          variant="destructive"
                          onClick={() => handleDeletePayment(alipayConfig.id)}
                        >
                          删除
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        setEditingPayment({ payment_type: "alipay" })
                        setShowPaymentForm(true)
                      }}
                    >
                      添加支付宝
                    </Button>
                  )}
                </div>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {/* VIP 套餐表单对话框 */}
      {showPlanForm && (
        <PlanFormDialog
          plan={editingPlan}
          onSave={handleSavePlan}
          onClose={() => {
            setShowPlanForm(false)
            setEditingPlan(null)
          }}
        />
      )}

      {/* 支付配置表单对话框 */}
      {showPaymentForm && (
        <PaymentFormDialog
          config={editingPayment}
          onSave={handleSavePayment}
          onClose={() => {
            setShowPaymentForm(false)
            setEditingPayment(null)
          }}
        />
      )}
    </>
  )
}

// VIP 套餐表单组件
function PlanFormDialog({ plan, onSave, onClose }: { plan: any; onSave: (plan: any) => void; onClose: () => void }) {
  const [name, setName] = useState(plan?.name || "")
  const [durationDays, setDurationDays] = useState(plan?.duration_days || 30)
  const [price, setPrice] = useState(plan?.price || "")
  const [description, setDescription] = useState(plan?.description || "")
  const [isActive, setIsActive] = useState(plan?.is_active !== false)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    onSave({
      name,
      duration_days: Number(durationDays),
      price,
      description: description || null,
      is_active: isActive,
    })
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <Card className="w-full max-w-md m-4">
        <CardHeader>
          <CardTitle>{plan ? "编辑套餐" : "添加套餐"}</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="plan-name">套餐名称</Label>
              <Input
                id="plan-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                placeholder="例如：月度VIP"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="plan-duration">时长（天）</Label>
              <Input
                id="plan-duration"
                type="number"
                value={durationDays}
                onChange={(e) => setDurationDays(Number(e.target.value))}
                required
                min="1"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="plan-price">价格</Label>
              <Input
                id="plan-price"
                value={price}
                onChange={(e) => setPrice(e.target.value)}
                required
                placeholder="例如：29.9"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="plan-description">描述（可选）</Label>
              <Input
                id="plan-description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="套餐描述"
              />
            </div>
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="plan-active"
                checked={isActive}
                onChange={(e) => setIsActive(e.target.checked)}
              />
              <Label htmlFor="plan-active">启用</Label>
            </div>
            <div className="flex gap-2">
              <Button type="submit" className="flex-1">保存</Button>
              <Button type="button" variant="outline" onClick={onClose} className="flex-1">取消</Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}

// 支付配置表单组件
function PaymentFormDialog({ config, onSave, onClose }: { config: any; onSave: (config: any) => void; onClose: () => void }) {
  const [accountName, setAccountName] = useState(config?.account_name || "")
  const [accountNumber, setAccountNumber] = useState(config?.account_number || "")
  const [qrCodeUrl, setQrCodeUrl] = useState(config?.qr_code_url || "")
  const [qrCodeFileId, setQrCodeFileId] = useState(config?.qr_code_file_id || "")
  const [isActive, setIsActive] = useState(config?.is_active !== false)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    onSave({
      payment_type: config.payment_type,
      account_name: accountName || null,
      account_number: accountNumber || null,
      qr_code_url: qrCodeUrl || null,
      qr_code_file_id: qrCodeFileId || null,
      is_active: isActive,
    })
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <Card className="w-full max-w-md m-4">
        <CardHeader>
          <CardTitle>配置{config.payment_type === "wechat" ? "微信" : "支付宝"}支付</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="payment-account-name">收款人姓名（可选）</Label>
              <Input
                id="payment-account-name"
                value={accountName}
                onChange={(e) => setAccountName(e.target.value)}
                placeholder="收款人姓名"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="payment-account-number">收款账号（可选）</Label>
              <Input
                id="payment-account-number"
                value={accountNumber}
                onChange={(e) => setAccountNumber(e.target.value)}
                placeholder="收款账号"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="payment-qr-url">二维码图片URL（可选）</Label>
              <Input
                id="payment-qr-url"
                value={qrCodeUrl}
                onChange={(e) => setQrCodeUrl(e.target.value)}
                placeholder="https://example.com/qr.png"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="payment-qr-file-id">二维码Telegram File ID（可选）</Label>
              <Input
                id="payment-qr-file-id"
                value={qrCodeFileId}
                onChange={(e) => setQrCodeFileId(e.target.value)}
                placeholder="上传二维码到Telegram后获取File ID"
              />
              <p className="text-xs text-muted-foreground">
                提示：将二维码图片发送给机器人，然后从消息中获取 file_id
              </p>
            </div>
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="payment-active"
                checked={isActive}
                onChange={(e) => setIsActive(e.target.checked)}
              />
              <Label htmlFor="payment-active">启用</Label>
            </div>
            <div className="flex gap-2">
              <Button type="submit" className="flex-1">保存</Button>
              <Button type="button" variant="outline" onClick={onClose} className="flex-1">取消</Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
