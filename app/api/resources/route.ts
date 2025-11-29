import { NextRequest, NextResponse } from "next/server"
import { cookies } from "next/headers"
import { adminFetch } from "@/lib/admin-api"

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url)
  const type = searchParams.get("type")
  const query =
    type && type !== "all" ? `?resource_type=${encodeURIComponent(type)}` : ""

  const cookieStore = await cookies()
  const token = cookieStore.get("admin_token")?.value
  if (!token) {
    return NextResponse.json({ message: "Unauthorized" }, { status: 401 })
  }

  const upstream = await adminFetch(`/resources${query}`, undefined, token)
  const body = await upstream.text()
  if (!body) {
    return NextResponse.json([], { status: upstream.status })
  }
  try {
    return NextResponse.json(JSON.parse(body), { status: upstream.status })
  } catch {
    return new NextResponse(body, {
      status: upstream.status,
      headers: { "content-type": upstream.headers.get("content-type") ?? "text/plain" },
    })
  }
}

