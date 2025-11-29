// 获取后端 API 地址
// 优先使用 ADMIN_API_BASE_URL，如果没有则根据环境判断
const getBaseUrl = () => {
  if (process.env.ADMIN_API_BASE_URL) {
    return process.env.ADMIN_API_BASE_URL
  }
  // 如果是服务器环境，尝试使用 localhost
  const port = process.env.WEB_PORT ?? "8000"
  // 检查是否在服务器环境（通过 NODE_ENV 或其他环境变量）
  if (process.env.NODE_ENV === "production" || process.env.SERVER_MODE === "true") {
    return `http://127.0.0.1:${port}`
  }
  return `http://127.0.0.1:${port}`
}

const BASE_URL = getBaseUrl()

export async function adminFetch(path: string, init?: RequestInit, token?: string) {
  const url = path.startsWith("http") ? path : `${BASE_URL}${path}`
  const headers = new Headers(init?.headers)
  if (token) {
    headers.set("Authorization", `Bearer ${token}`)
  }
  const response = await fetch(url, {
    ...init,
    headers,
  })
  return response
}

