const BASE_URL =
  process.env.ADMIN_API_BASE_URL ??
  `http://127.0.0.1:${process.env.WEB_PORT ?? "8080"}`

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

