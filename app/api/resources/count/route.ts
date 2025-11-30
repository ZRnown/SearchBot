import { NextRequest, NextResponse } from "next/server"
import { cookies } from "next/headers"
import { adminFetch } from "@/lib/admin-api"

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url)
  const type = searchParams.get("resource_type")
  const query = type ? `?resource_type=${encodeURIComponent(type)}` : ""

  const cookieStore = await cookies()
  const token = cookieStore.get("admin_token")?.value
  if (!token) {
    return NextResponse.json({ message: "Unauthorized" }, { status: 401 })
  }

  const upstream = await adminFetch(`/resources/count${query}`, undefined, token)
  const data = await upstream.json()
  return NextResponse.json(data)
}

