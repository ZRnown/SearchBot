// 获取后端 API 地址
// 优先使用 ADMIN_API_BASE_URL，如果没有则使用默认值
const getBaseUrl = () => {
  if (process.env.ADMIN_API_BASE_URL) {
    return process.env.ADMIN_API_BASE_URL
  }
  // 默认使用 localhost，端口从环境变量获取，默认8080
  const port = process.env.WEB_PORT ?? "8080"
  return `http://127.0.0.1:${port}`
}

const BASE_URL = getBaseUrl()

// 调试：输出 BASE_URL（仅在开发环境）
if (process.env.NODE_ENV !== "production") {
  console.log("[admin-api] BASE_URL:", BASE_URL)
}

export async function adminFetch(path: string, init?: RequestInit, token?: string) {
  const url = path.startsWith("http") ? path : `${BASE_URL}${path}`
  const headers = new Headers(init?.headers)
  if (token) {
    headers.set("Authorization", `Bearer ${token}`)
  }
  // 如果有 body 且是字符串，确保设置 Content-Type
  if (init?.body && typeof init.body === 'string' && !headers.has('Content-Type')) {
    headers.set("Content-Type", "application/json")
  }
  const response = await fetch(url, {
    ...init,
    headers,
  })
  return response
}

