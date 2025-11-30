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
import { Search, Trash2, Edit, Crown, Ban } from "lucide-react"
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from "@/components/ui/pagination"
import { useToast } from "@/components/ui/use-toast"
import {
  fetchUsers,
  updateUser,
  deleteUser,
  batchDeleteUsers,
  type UserRecord,
} from "@/lib/api"

export function UserManager() {
  const [users, setUsers] = useState<UserRecord[]>([])
  const [loading, setLoading] = useState(false)
  const [search, setSearch] = useState("")
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set())
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [batchDeleteDialogOpen, setBatchDeleteDialogOpen] = useState(false)
  const [editingUser, setEditingUser] = useState<UserRecord | null>(null)
  const [deletingUserId, setDeletingUserId] = useState<number | null>(null)
  const [vipLoadingId, setVipLoadingId] = useState<number | null>(null)
  const [page, setPage] = useState(1)
  const [totalCount, setTotalCount] = useState(0)
  const pageSize = 50
  const { toast } = useToast()

  useEffect(() => {
    loadUsers()
  }, [search, page])

  const loadUsers = async () => {
    try {
      setLoading(true)
      const skip = (page - 1) * pageSize
      const data = await fetchUsers(search || undefined, skip, pageSize)
      setUsers(data)
      setSelectedIds(new Set())
      
      // 获取总数
      const countParams = new URLSearchParams()
      if (search) {
        countParams.append("search", search)
      }
      const countResponse = await fetch(`/api/users/count?${countParams.toString()}`)
      if (countResponse.ok) {
        const countData = await countResponse.json()
        setTotalCount(countData.count || 0)
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "加载失败"
      toast({
        title: "加载用户失败",
        description: message,
        variant: "destructive",
      })
    } finally {
      setLoading(false)
    }
  }
  
  // 当搜索改变时，重置到第一页
  useEffect(() => {
    setPage(1)
  }, [search])

  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      setSelectedIds(new Set(users.map((u) => u.userId)))
    } else {
      setSelectedIds(new Set())
    }
  }

  const handleSelectOne = (userId: number, checked: boolean) => {
    const next = new Set(selectedIds)
    if (checked) {
      next.add(userId)
    } else {
      next.delete(userId)
    }
    setSelectedIds(next)
  }

  const handleDelete = async (userId: number) => {
    try {
      await deleteUser(userId)
      toast({ title: "已删除用户" })
      await loadUsers()
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
      await batchDeleteUsers(Array.from(selectedIds))
      toast({ title: `已删除 ${selectedIds.size} 个用户` })
      setBatchDeleteDialogOpen(false)
      await loadUsers()
    } catch (error) {
      const message = error instanceof Error ? error.message : "批量删除失败"
      toast({
        title: "批量删除失败",
        description: message,
        variant: "destructive",
      })
    }
  }

  const handleSave = async (user: Partial<UserRecord>) => {
    if (!editingUser) return
    try {
      await updateUser(editingUser.userId, user)
      toast({ title: "已更新用户" })
      setEditingUser(null)
      await loadUsers()
    } catch (error) {
      const message = error instanceof Error ? error.message : "保存失败"
      toast({
        title: "保存失败",
        description: message,
        variant: "destructive",
      })
    }
  }

  const isVip = (user: UserRecord) => {
    if (!user.vipExpiry) return false
    return new Date(user.vipExpiry) > new Date()
  }

  const handleGrantVip = async (userId: number, days = 30) => {
    try {
      setVipLoadingId(userId)
      const expiry = new Date()
      expiry.setDate(expiry.getDate() + days)
      await updateUser(userId, { vipExpiry: expiry.toISOString() })
      toast({ title: `已为用户添加 ${days} 天 VIP` })
      await loadUsers()
    } catch (error) {
      const message = error instanceof Error ? error.message : "设置 VIP 失败"
      toast({
        title: "设置 VIP 失败",
        description: message,
        variant: "destructive",
      })
    } finally {
      setVipLoadingId(null)
    }
  }

  const handleRemoveVip = async (userId: number) => {
    try {
      setVipLoadingId(userId)
      await updateUser(userId, { vipExpiry: null })
      toast({ title: "已取消用户 VIP" })
      await loadUsers()
    } catch (error) {
      const message = error instanceof Error ? error.message : "取消 VIP 失败"
      toast({
        title: "取消 VIP 失败",
        description: message,
        variant: "destructive",
      })
    } finally {
      setVipLoadingId(null)
    }
  }

  return (
    <>
      <Card className="w-full">
        <CardHeader>
          <CardTitle>用户管理</CardTitle>
          <div className="flex flex-col sm:flex-row gap-3 mt-4">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="搜索用户（ID、用户名、昵称）..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-9"
              />
            </div>
            <div className="flex gap-2">
              {selectedIds.size > 0 && (
                <Button
                  variant="destructive"
                  onClick={() => setBatchDeleteDialogOpen(true)}
                >
                  <Trash2 className="h-4 w-4 mr-2" />
                  批量删除 ({selectedIds.size})
                </Button>
              )}
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="rounded-lg border border-border overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow className="bg-muted/50">
                  <TableHead className="w-12">
                    <Checkbox
                      checked={selectedIds.size === users.length && users.length > 0}
                      onCheckedChange={handleSelectAll}
                    />
                  </TableHead>
                  <TableHead>用户ID</TableHead>
                  <TableHead>昵称</TableHead>
                  <TableHead>用户名</TableHead>
                  <TableHead>VIP</TableHead>
                  <TableHead>VIP到期</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead className="w-40 text-right">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {users.map((user) => (
                  <TableRow key={user.userId}>
                    <TableCell>
                      <Checkbox
                        checked={selectedIds.has(user.userId)}
                        onCheckedChange={(checked) =>
                          handleSelectOne(user.userId, checked as boolean)
                        }
                      />
                    </TableCell>
                    <TableCell className="font-mono text-sm">{user.userId}</TableCell>
                    <TableCell>{user.firstName || "-"}</TableCell>
                    <TableCell>@{user.username || "-"}</TableCell>
                    <TableCell>
                      {isVip(user) ? (
                        <Badge className="bg-warning text-warning-foreground">
                          <Crown className="h-3 w-3 mr-1" />
                          VIP
                        </Badge>
                      ) : (
                        <span className="text-muted-foreground text-sm">普通</span>
                      )}
                    </TableCell>
                    <TableCell className="text-sm">
                      {user.vipExpiry
                        ? new Date(user.vipExpiry).toLocaleDateString("zh-CN")
                        : "-"}
                    </TableCell>
                    <TableCell>
                      {user.isBlocked ? (
                        <Badge variant="destructive">
                          <Ban className="h-3 w-3 mr-1" />
                          已封禁
                        </Badge>
                      ) : (
                        <Badge variant="secondary">正常</Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex flex-wrap justify-end gap-2">
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => setEditingUser(user)}
                        >
                          <Edit className="h-4 w-4" />
                        </Button>
                        {isVip(user) ? (
                          <Button
                            variant="outline"
                            size="icon"
                            title="取消 VIP"
                            disabled={vipLoadingId === user.userId}
                            onClick={() => handleRemoveVip(user.userId)}
                          >
                            <Ban className="h-4 w-4" />
                          </Button>
                        ) : (
                          <Button
                            variant="secondary"
                            size="icon"
                            title="赋予 30 天 VIP"
                            disabled={vipLoadingId === user.userId}
                            onClick={() => handleGrantVip(user.userId)}
                          >
                            <Crown className="h-4 w-4" />
                          </Button>
                        )}
                        <Button
                          variant="destructive"
                          size="icon"
                          onClick={() => {
                            setDeletingUserId(user.userId)
                            setDeleteDialogOpen(true)
                          }}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
                {loading && (
                  <TableRow>
                    <TableCell colSpan={8} className="text-center py-8 text-muted-foreground">
                      正在加载数据...
                    </TableCell>
                  </TableRow>
                )}
                {!loading && users.length === 0 && (
                  <TableRow>
                  <TableCell colSpan={8} className="text-center py-8 text-muted-foreground">
                    未找到用户
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>
          {totalCount > pageSize && (
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
              确定要删除这个用户吗？此操作不可恢复。
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => {
              setDeleteDialogOpen(false)
              setDeletingUserId(null)
            }}>
              取消
            </Button>
            <Button
              variant="destructive"
              onClick={async () => {
                if (deletingUserId) {
                  await handleDelete(deletingUserId)
                  setDeleteDialogOpen(false)
                  setDeletingUserId(null)
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
              确定要删除选中的 {selectedIds.size} 个用户吗？此操作不可恢复。
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

      {editingUser && (
        <UserEditDialog
          open={editingUser !== null}
          user={editingUser}
          onClose={() => setEditingUser(null)}
          onSave={handleSave}
        />
      )}
    </>
  )
}

function UserEditDialog({
  open,
  user,
  onClose,
  onSave,
}: {
  open: boolean
  user: UserRecord | null
  onClose: () => void
  onSave: (user: Partial<UserRecord>) => Promise<void>
}) {
  const [vipExpiry, setVipExpiry] = useState("")

  useEffect(() => {
    if (user?.vipExpiry) {
      setVipExpiry(new Date(user.vipExpiry).toISOString().split("T")[0])
    } else {
      setVipExpiry("")
    }
  }, [user, open])

  if (!user) {
    return null
  }

  const handleSubmit = async () => {
    await onSave({
      vipExpiry: vipExpiry ? new Date(vipExpiry).toISOString() : null,
    })
  }

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>设置 VIP 到期时间</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 py-4">
          <div>
            <p className="text-sm text-muted-foreground">用户 ID</p>
            <p className="font-mono text-base">{user.userId}</p>
          </div>
          <div>
            <p className="text-sm text-muted-foreground">昵称 / 用户名</p>
            <p className="text-base">
              {user.firstName || "-"} {user.username ? `(@${user.username})` : ""}
            </p>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium">VIP 到期日期</label>
            <Input type="date" value={vipExpiry} onChange={(e) => setVipExpiry(e.target.value)} />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            取消
          </Button>
          <Button onClick={handleSubmit}>保存</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

