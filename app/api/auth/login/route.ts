import { NextResponse } from "next/server"
import { adminFetch } from "@/lib/admin-api"

export async function POST(request: Request) {
  const payload = await request.json()
  const upstream = await adminFetch("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
  const text = await upstream.text()
  let data: any = {}
  if (text) {
    try {
      data = JSON.parse(text)
    } catch {
      return new NextResponse(text, { status: upstream.status })
    }
  }
  if (!upstream.ok) {
    return NextResponse.json(data, { status: upstream.status })
  }
  const response = NextResponse.json({ username: payload.username })
  response.cookies.set("admin_token", data.access_token, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: data.expires_in ?? 3600,
  })
  return response
}

