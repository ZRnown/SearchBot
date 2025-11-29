import { NextResponse } from "next/server"
import { cookies } from "next/headers"
import { adminFetch } from "@/lib/admin-api"

export async function POST(request: Request) {
  const payload = await request.json()
  const cookieStore = await cookies()
  const token = cookieStore.get("admin_token")?.value
  if (!token) {
    return NextResponse.json({ message: "Unauthorized" }, { status: 401 })
  }
  const upstream = await adminFetch(
    "/resources/indexed",
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    },
    token,
  )
  const text = await upstream.text()
  if (!text) {
    return NextResponse.json({}, { status: upstream.status })
  }
  try {
    return NextResponse.json(JSON.parse(text), { status: upstream.status })
  } catch {
    return new NextResponse(text, {
      status: upstream.status,
      headers: { "content-type": upstream.headers.get("content-type") ?? "text/plain" },
    })
  }
}

