import { NextRequest, NextResponse } from "next/server"
import { cookies } from "next/headers"
import { adminFetch } from "@/lib/admin-api"

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url)
  const search = searchParams.get("search")
  const query = search ? `?search=${encodeURIComponent(search)}` : ""

  const cookieStore = await cookies()
  const token = cookieStore.get("admin_token")?.value
  if (!token) {
    return NextResponse.json({ message: "Unauthorized" }, { status: 401 })
  }

  const upstream = await adminFetch(`/users/count${query}`, undefined, token)
  const data = await upstream.json()
  return NextResponse.json(data)
}

