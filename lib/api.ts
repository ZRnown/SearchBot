export type ResourceRecord = {
  id: string
  title: string
  type: "novel" | "audio" | "comic"
  isVip: boolean
  link: string
  previewLink?: string | null
  deepLink?: string | null
  createdAt: string
}

export type ComicUploadResult = {
  id: string
  pages: number
  deepLink: string
  previewLink: string
}

export type ComicFileRecord = {
  id: number
  fileId: string
  order: number
}

export type ComicFilesData = {
  resourceId: string
  title: string
  files: ComicFileRecord[]
}

export type SearchButtonRecord = {
  id: number
  label: string
  url: string
  sortOrder: number
}

export type SettingsPayload = {
  pageSize: number
  searchChannelId: number
  comicPreviewChannelId: number
  storageChannelId: number
}

export type UserRecord = {
  userId: number
  firstName: string | null
  username: string | null
  vipExpiry: string | null
  isBlocked: boolean
  usageQuota: number
  createdAt: string
  updatedAt: string
}

async function handleJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const text = await response.text()
    throw new Error(text || `Request failed with status ${response.status}`)
  }
  return (await response.json()) as T
}

export async function fetchResources(filter: "all" | "novel" | "audio" | "comic" = "all") {
  const query = filter !== "all" ? `?type=${filter}` : ""
  const response = await fetch(`/api/resources${query}`, { cache: "no-store" })
  const data = await handleJson<any[]>(response)
  return data.map((item) => ({
    id: item.id,
    title: item.title,
    type: item.type,
    isVip: item.is_vip,
    link: item.link,
    previewLink: item.preview_link,
    deepLink: item.deep_link,
    createdAt: item.created_at,
  })) as ResourceRecord[]
}

export async function createIndexedResource(payload: {
  title: string
  type: "novel" | "audio"
  jump_url: string
}) {
  const response = await fetch("/api/resources/indexed", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
  const item = await handleJson<any>(response)
  return {
    id: item.id,
    title: item.title,
    type: item.type,
    isVip: item.is_vip ?? false,
    link: item.link,
    previewLink: item.preview_link ?? item.link,
    deepLink: null,
    createdAt: new Date().toISOString(),
  } as ResourceRecord
}

export async function deleteResource(resourceId: string) {
  const response = await fetch(`/api/resources/${resourceId}`, { method: "DELETE" })
  if (!response.ok) {
    const message = await response.text()
    throw new Error(message || "删除失败")
  }
}

export async function batchDeleteResources(resourceIds: string[]) {
  const response = await fetch("/api/resources/batch-delete", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(resourceIds),
  })
  if (!response.ok) {
    const message = await response.text()
    throw new Error(message || "批量删除失败")
  }
}

export async function updateResource(resourceId: string, payload: {
  title?: string
  jump_url?: string
  preview_url?: string
}) {
  const response = await fetch(`/api/resources/${resourceId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
  const item = await handleJson<any>(response)
  return {
    id: item.id,
    title: item.title,
    type: item.type,
    isVip: item.is_vip,
    link: item.link,
    previewLink: item.preview_link,
    deepLink: item.deep_link,
    createdAt: item.created_at,
  } as ResourceRecord
}

export async function uploadComic(payload: { title: string; isVip: boolean; files: File[] }) {
  const form = new FormData()
  form.append("title", payload.title)
  form.append("is_vip", String(payload.isVip))
  form.append("preview_count", "5")  // 默认发送前5张预览图
  payload.files.forEach((file) => form.append("files", file, file.name))
  const response = await fetch("/api/resources/comics", {
    method: "POST",
    body: form,
  })
  const data = await handleJson<any>(response)
  return {
    id: data.id,
    pages: data.pages,
    deepLink: data.deep_link,
    previewLink: data.preview_link,
  } as ComicUploadResult
}

export async function uploadComicArchive(payload: {
  title: string
  isVip: boolean
  archive: File
  previewCount?: number
}) {
  const form = new FormData()
  form.append("title", payload.title)
  form.append("is_vip", String(payload.isVip))
  form.append("archive", payload.archive, payload.archive.name)
  form.append("preview_count", String(payload.previewCount ?? 5))
  const response = await fetch("/api/resources/comics/archive", {
    method: "POST",
    body: form,
  })
  const data = await handleJson<any>(response)
  return {
    id: data.id,
    pages: data.pages,
    deepLink: data.deep_link,
    previewLink: data.preview_link,
  } as ComicUploadResult
}

export async function batchUploadComicArchives(payload: {
  archives: File[]
  isVip: boolean
  previewCount?: number
}) {
  const form = new FormData()
  form.append("is_vip", String(payload.isVip))
  form.append("preview_count", String(payload.previewCount ?? 5))
  payload.archives.forEach((archive) => {
    form.append("archives", archive, archive.name)
  })
  const response = await fetch("/api/resources/comics/batch-archive", {
    method: "POST",
    body: form,
  })
  const data = await handleJson<any[]>(response)
  return data.map((item) => ({
    id: item.id,
    pages: item.pages,
    deepLink: item.deep_link,
    previewLink: item.preview_link || item.deep_link,
  })) as ComicUploadResult[]
}

export async function getComicFiles(resourceId: string) {
  const response = await fetch(`/api/resources/comics/${resourceId}/files`, {
    cache: "no-store",
  })
  const data = await handleJson<any>(response)
  return {
    resourceId: data.resource_id,
    title: data.title,
    files: data.files.map((f: any) => ({
      id: f.id,
      fileId: f.file_id,
      order: f.order,
    })),
  } as ComicFilesData
}

export async function updateComicFilesOrder(
  resourceId: string,
  fileOrders: Array<{ id: number; order: number }>
) {
  const response = await fetch(`/api/resources/comics/${resourceId}/files/order`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ file_orders: fileOrders }),
  })
  await handleJson(response)
}

export async function getComicFileUrl(fileId: string): Promise<string> {
  const response = await fetch(`/api/resources/comics/files/${fileId}/url`, {
    cache: "no-store",
  })
  const data = await handleJson<{ url: string }>(response)
  return data.url
}

export async function fetchSettings() {
  const response = await fetch("/api/settings", { cache: "no-store" })
  const data = await handleJson<any>(response)
  return {
    pageSize: data.page_size,
    searchChannelId: data.search_channel_id,
    comicPreviewChannelId: data.comic_preview_channel_id,
    storageChannelId: data.storage_channel_id,
  } as SettingsPayload
}

export async function fetchUsers(search?: string) {
  const query = search ? `?search=${encodeURIComponent(search)}` : ""
  const response = await fetch(`/api/users${query}`, { cache: "no-store" })
  const data = await handleJson<any[]>(response)
  return data.map((item) => ({
    userId: item.user_id,
    firstName: item.first_name,
    username: item.username,
    vipExpiry: item.vip_expiry,
    isBlocked: item.is_blocked,
    usageQuota: item.usage_quota,
    createdAt: item.created_at,
    updatedAt: item.updated_at,
  })) as UserRecord[]
}

export async function updateUser(userId: number, payload: Partial<UserRecord>) {
  const body: Record<string, unknown> = {}
  if (payload.firstName !== undefined) {
    body.first_name = payload.firstName
  }
  if (payload.username !== undefined) {
    body.username = payload.username
  }
  if (payload.vipExpiry !== undefined) {
    body.vip_expiry = payload.vipExpiry
  }
  if (payload.isBlocked !== undefined) {
    body.is_blocked = payload.isBlocked
  }
  const response = await fetch(`/api/users/${userId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  const item = await handleJson<any>(response)
  return {
    userId: item.user_id,
    firstName: item.first_name,
    username: item.username,
    vipExpiry: item.vip_expiry,
    isBlocked: item.is_blocked,
    usageQuota: item.usage_quota,
    createdAt: item.created_at,
    updatedAt: item.updated_at,
  } as UserRecord
}

export async function deleteUser(userId: number) {
  const response = await fetch(`/api/users/${userId}`, { method: "DELETE" })
  if (!response.ok) {
    const message = await response.text()
    throw new Error(message || "删除失败")
  }
}

export async function batchDeleteUsers(userIds: number[]) {
  const response = await fetch("/api/users/batch-delete", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(userIds),
  })
  if (!response.ok) {
    const message = await response.text()
    throw new Error(message || "批量删除失败")
  }
}

export async function fetchSearchButtons() {
  const response = await fetch("/api/search-buttons", { cache: "no-store" })
  const data = await handleJson<any[]>(response)
  return data.map((item) => ({
    id: item.id,
    label: item.label,
    url: item.url,
    sortOrder: item.sort_order,
  })) as SearchButtonRecord[]
}

export async function createSearchButton(payload: { label: string; url: string; sort_order: number }) {
  const response = await fetch("/api/search-buttons", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
  const item = await handleJson<any>(response)
  return {
    id: item.id,
    label: item.label,
    url: item.url,
    sortOrder: item.sort_order,
  } as SearchButtonRecord
}

export async function updateSearchButton(
  buttonId: number,
  payload: { label: string; url: string; sort_order: number },
) {
  const response = await fetch(`/api/search-buttons/${buttonId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
  const item = await handleJson<any>(response)
  return {
    id: item.id,
    label: item.label,
    url: item.url,
    sortOrder: item.sort_order,
  } as SearchButtonRecord
}

export async function deleteSearchButton(buttonId: number) {
  const response = await fetch(`/api/search-buttons/${buttonId}`, { method: "DELETE" })
  if (!response.ok) {
    const text = await response.text()
    throw new Error(text || "删除失败")
  }
}

