import { NextResponse } from "next/server"
import { cookies } from "next/headers"
import { adminFetch } from "@/lib/admin-api"

type RouteParams = { params: Promise<{ id: string }> }

export async function DELETE(_: Request, { params }: RouteParams) {
  const cookieStore = await cookies()
  const token = cookieStore.get("admin_token")?.value
  if (!token) {
    return NextResponse.json({ message: "Unauthorized" }, { status: 401 })
  }
  const { id } = await params
  const upstream = await adminFetch(
    `/resources/${id}`,
    {
      method: "DELETE",
    },
    token,
  )
  return new NextResponse(null, { status: upstream.status })
}

export async function PUT(request: Request, { params }: RouteParams) {
  const cookieStore = await cookies()
  const token = cookieStore.get("admin_token")?.value
  if (!token) {
    return NextResponse.json({ message: "Unauthorized" }, { status: 401 })
  }
  const { id } = await params
  const payload = await request.json()
  const upstream = await adminFetch(
    `/resources/${id}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
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
    return new NextResponse(text, { status: upstream.status })
  }
}

