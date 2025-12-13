"use client"

import { useEffect, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Button } from "@/components/ui/button"
import { useToast } from "@/components/ui/use-toast"
import { Spinner } from "@/components/ui/spinner"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"

// 管理后台中的 VIP 套餐和支付配置面板
export function VipSettings() {
  const [vipPlans, setVipPlans] = useState<any[]>([])
  const [paymentConfigs, setPaymentConfigs] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [showPlanForm, setShowPlanForm] = useState(false)
  const [showPaymentForm, setShowPaymentForm] = useState(false)
  const [editingPlan, setEditingPlan] = useState<any>(null)
  const [editingPayment, setEditingPayment] = useState<any>(null)
  const [savingPlan, setSavingPlan] = useState(false)
  const [savingPayment, setSavingPayment] = useState(false)
  const [deletingPlanId, setDeletingPlanId] = useState<number | null>(null)
  const [deletingPaymentId, setDeletingPaymentId] = useState<number | null>(null)
  const [showDeletePlanDialog, setShowDeletePlanDialog] = useState(false)
  const [showDeletePaymentDialog, setShowDeletePaymentDialog] = useState(false)
  const [planToDelete, setPlanToDelete] = useState<{ id: number; name: string } | null>(null)
  const [paymentToDelete, setPaymentToDelete] = useState<{ id: number; payment_type: string } | null>(null)
  const { toast } = useToast()

  useEffect(() => {
    void loadData()
  }, [])

  const loadData = async () => {
    try {
      setLoading(true)
      const [plansRes, configsRes] = await Promise.all([
        fetch("/api/vip-plans"),
        fetch("/api/shark-payment-configs"),
      ])
      if (plansRes.ok) {
        const plans = await plansRes.json()
        setVipPlans(plans)
      } else {
        const body = await plansRes.json().catch(() => ({}))
        throw new Error(body.detail ?? "加载VIP套餐失败")
      }
      if (configsRes.ok) {
        const configs = await configsRes.json()
        setPaymentConfigs(configs)
      } else {
        const body = await configsRes.json().catch(() => ({}))
        throw new Error(body.detail ?? "加载支付配置失败")
      }
      toast({
        title: "加载成功",
        description: "VIP套餐和支付配置已加载",
      })
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
      setSavingPlan(true)
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
      await loadData()
    } catch (error) {
      toast({
        title: "保存失败",
        description: error instanceof Error ? error.message : "请稍后再试",
        variant: "destructive",
      })
    } finally {
      setSavingPlan(false)
    }
  }

  const handleDeletePlanClick = (plan: { id: number; name: string }) => {
    setPlanToDelete(plan)
    setShowDeletePlanDialog(true)
  }

  const handleDeletePlanConfirm = async () => {
    if (!planToDelete) return
    try {
      setDeletingPlanId(planToDelete.id)
      setShowDeletePlanDialog(false)
      const res = await fetch(`/api/vip-plans/${planToDelete.id}`, { method: "DELETE" })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.detail ?? "删除失败")
      }
      toast({ 
        title: "删除成功",
        description: `套餐 "${planToDelete.name}" 已删除`,
      })
      await loadData()
    } catch (error) {
      toast({
        title: "删除失败",
        description: error instanceof Error ? error.message : "请稍后再试",
        variant: "destructive",
      })
    } finally {
      setDeletingPlanId(null)
      setPlanToDelete(null)
    }
  }

  const handleSavePayment = async (config: any) => {
    try {
      setSavingPayment(true)
      const url = editingPayment ? `/api/shark-payment-configs/${editingPayment.id}` : "/api/shark-payment-configs"
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
      await loadData()
    } catch (error) {
      toast({
        title: "保存失败",
        description: error instanceof Error ? error.message : "请稍后再试",
        variant: "destructive",
      })
    } finally {
      setSavingPayment(false)
    }
  }

  const handleDeletePaymentClick = (config: { id: number; payment_type: string }) => {
    setPaymentToDelete(config)
    setShowDeletePaymentDialog(true)
  }

  const handleDeletePaymentConfirm = async () => {
    if (!paymentToDelete) return
    try {
      setDeletingPaymentId(paymentToDelete.id)
      setShowDeletePaymentDialog(false)
      const res = await fetch(`/api/shark-payment-configs/${paymentToDelete.id}`, { method: "DELETE" })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.detail ?? "删除失败")
      }
      toast({ 
        title: "删除成功",
        description: `${paymentToDelete.payment_type === "wechat" ? "微信" : "支付宝"}支付配置已删除`,
      })
      await loadData()
    } catch (error) {
      toast({
        title: "删除失败",
        description: error instanceof Error ? error.message : "请稍后再试",
        variant: "destructive",
      })
    } finally {
      setDeletingPaymentId(null)
      setPaymentToDelete(null)
    }
  }

  const paymentConfig = paymentConfigs.length > 0 ? paymentConfigs[0] : null

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
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Spinner />
              <span>加载中...</span>
            </div>
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
                      onClick={() => handleDeletePlanClick({ id: plan.id, name: plan.name })}
                      disabled={deletingPlanId === plan.id || loading}
                    >
                      {deletingPlanId === plan.id && <Spinner className="mr-1" />}
                      删除
                    </Button>
                  </div>
                </div>
              ))}
              <Button 
                onClick={() => {
                  setEditingPlan(null)
                  setShowPlanForm(true)
                }} 
                className="w-full" 
                disabled={savingPlan || loading}
              >
                {savingPlan && <Spinner className="mr-2" />}
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
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Spinner />
              <span>加载中...</span>
            </div>
          ) : (
            <>
              <div className="space-y-3">
                {paymentConfig ? (
                <div className="p-3 rounded-lg bg-muted">
                    <p className="font-medium text-sm mb-2">鲨鱼支付配置</p>
                    <div className="space-y-1">
                      <p className="text-xs text-muted-foreground">商户号：{paymentConfig.merchant_id}</p>
                      <p className="text-xs text-muted-foreground">API地址：{paymentConfig.api_base_url}</p>
                      <p className="text-xs text-muted-foreground">回调地址：{paymentConfig.notify_url}</p>
                      {paymentConfig.channel_type && (
                        <p className="text-xs text-muted-foreground">通道类型：{paymentConfig.channel_type}</p>
                      )}
                      <p className="text-xs text-muted-foreground">
                        状态：{paymentConfig.is_active ? "✅ 已启用" : "❌ 已禁用"}
                      </p>
                      <div className="flex gap-2 mt-2">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => {
                            setEditingPayment(paymentConfig)
                            setShowPaymentForm(true)
                          }}
                        >
                          编辑
                        </Button>
                        <Button
                          size="sm"
                          variant="destructive"
                          onClick={() => handleDeletePaymentClick({ id: paymentConfig.id, payment_type: "shark" })}
                          disabled={deletingPaymentId === paymentConfig.id || loading}
                        >
                          {deletingPaymentId === paymentConfig.id && <Spinner className="mr-1" />}
                          删除
                        </Button>
                      </div>
                      </div>
                    </div>
                  ) : (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => {
                      setEditingPayment(null)
                        setShowPaymentForm(true)
                      }}
                      disabled={savingPayment || loading}
                    className="w-full"
                    >
                      {savingPayment && <Spinner className="mr-2" />}
                    添加支付配置
                    </Button>
                  )}
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {/* VIP 套餐表单对话框 */}
      {showPlanForm && (
        <PlanFormDialog
          plan={editingPlan}
          loading={savingPlan}
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
          loading={savingPayment}
          onSave={handleSavePayment}
          onClose={() => {
            setShowPaymentForm(false)
            setEditingPayment(null)
          }}
        />
      )}

      {/* 删除套餐确认对话框 */}
      <AlertDialog open={showDeletePlanDialog} onOpenChange={setShowDeletePlanDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>确认删除套餐</AlertDialogTitle>
            <AlertDialogDescription>
              确定要删除套餐 "<strong>{planToDelete?.name}</strong>" 吗？此操作无法撤销。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deletingPlanId !== null}>取消</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeletePlanConfirm}
              disabled={deletingPlanId !== null}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deletingPlanId !== null && <Spinner className="mr-2" />}
              删除
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* 删除支付配置确认对话框 */}
      <AlertDialog open={showDeletePaymentDialog} onOpenChange={setShowDeletePaymentDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>确认删除支付配置</AlertDialogTitle>
            <AlertDialogDescription>
              确定要删除鲨鱼支付配置吗？此操作无法撤销。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deletingPaymentId !== null}>取消</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeletePaymentConfirm}
              disabled={deletingPaymentId !== null}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deletingPaymentId !== null && <Spinner className="mr-2" />}
              删除
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}

// VIP 套餐表单组件
function PlanFormDialog({
  plan,
  loading,
  onSave,
  onClose,
}: {
  plan: any
  loading: boolean
  onSave: (plan: any) => void
  onClose: () => void
}) {
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
              <Button type="submit" className="flex-1" disabled={loading}>
                {loading && <Spinner className="mr-2" />}
                {loading ? "保存中..." : "保存"}
              </Button>
              <Button type="button" variant="outline" onClick={onClose} className="flex-1" disabled={loading}>
                取消
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}

// 支付配置表单组件
function PaymentFormDialog({
  config,
  loading,
  onSave,
  onClose,
}: {
  config: any
  loading: boolean
  onSave: (config: any) => void
  onClose: () => void
}) {
  const [merchantId, setMerchantId] = useState(config?.merchant_id || "")
  const [signKey, setSignKey] = useState(config?.sign_key || "")
  const [apiBaseUrl, setApiBaseUrl] = useState(config?.api_base_url || "")
  const [notifyUrl, setNotifyUrl] = useState(config?.notify_url || "")
  const [returnUrl, setReturnUrl] = useState(config?.return_url || "")
  const [channelType, setChannelType] = useState(config?.channel_type || "")
  const [isActive, setIsActive] = useState(config?.is_active !== false)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    onSave({
      merchant_id: merchantId,
      sign_key: signKey,
      api_base_url: apiBaseUrl,
      notify_url: notifyUrl,
      return_url: returnUrl || null,
      channel_type: channelType || null,
      is_active: isActive,
    })
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <Card className="w-full max-w-md m-4 max-h-[90vh] overflow-y-auto">
        <CardHeader>
          <CardTitle>{config ? "编辑支付配置" : "添加支付配置"}</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="merchant-id">商户号 *</Label>
              <Input
                id="merchant-id"
                value={merchantId}
                onChange={(e) => setMerchantId(e.target.value)}
                required
                placeholder="例如：10242"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="sign-key">签名密钥 *</Label>
              <Input
                id="sign-key"
                type="password"
                value={signKey}
                onChange={(e) => setSignKey(e.target.value)}
                required
                placeholder="商户签名密钥"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="api-base-url">API基础地址 *</Label>
              <Input
                id="api-base-url"
                value={apiBaseUrl}
                onChange={(e) => setApiBaseUrl(e.target.value)}
                required
                placeholder="例如：http://qingju.lucky777.life"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="notify-url">异步通知地址 *</Label>
              <Input
                id="notify-url"
                value={notifyUrl}
                onChange={(e) => setNotifyUrl(e.target.value)}
                required
                placeholder="例如：http://your-domain.com/payment/notify"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="return-url">同步跳转地址（可选）</Label>
              <Input
                id="return-url"
                value={returnUrl}
                onChange={(e) => setReturnUrl(e.target.value)}
                placeholder="支付成功后的跳转地址"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="channel-type">通道类型（可选）</Label>
              <Input
                id="channel-type"
                value={channelType}
                onChange={(e) => setChannelType(e.target.value)}
                placeholder="通道编号，留空使用商户后台默认"
              />
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
              <Button type="submit" className="flex-1" disabled={loading}>
                {loading && <Spinner className="mr-2" />}
                {loading ? "保存中..." : "保存"}
              </Button>
              <Button type="button" variant="outline" onClick={onClose} className="flex-1" disabled={loading}>
                取消
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}


