import { NextResponse } from "next/server"
import { cookies } from "next/headers"
import { adminFetch } from "@/lib/admin-api"

export async function PUT(
  request: Request,
  { params }: { params: { id: string } }
) {
  const cookieStore = await cookies()
  const token = cookieStore.get("admin_token")?.value
  if (!token) {
    return NextResponse.json({ message: "Unauthorized" }, { status: 401 })
  }
  const body = await request.json()
  const upstream = await adminFetch(`/vip-plans/${params.id}`, { method: "PUT", body: JSON.stringify(body) }, token)
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

export async function DELETE(
  request: Request,
  { params }: { params: { id: string } }
) {
  const cookieStore = await cookies()
  const token = cookieStore.get("admin_token")?.value
  if (!token) {
    return NextResponse.json({ message: "Unauthorized" }, { status: 401 })
  }
  const upstream = await adminFetch(`/vip-plans/${params.id}`, { method: "DELETE" }, token)
  return new NextResponse(null, { status: upstream.status })
}

