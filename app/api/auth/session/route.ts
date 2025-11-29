import { NextResponse } from "next/server"
import { cookies } from "next/headers"
import { adminFetch } from "@/lib/admin-api"

export async function GET() {
  const cookieStore = await cookies()
  const token = cookieStore.get("admin_token")?.value
  if (!token) {
    return NextResponse.json({ message: "Unauthorized" }, { status: 401 })
  }
  const upstream = await adminFetch("/auth/profile", undefined, token)
  const text = await upstream.text()
  if (!text) {
    return NextResponse.json({ message: "Unauthorized" }, { status: 401 })
  }
  try {
    const data = JSON.parse(text)
    return NextResponse.json(data, { status: upstream.status })
  } catch {
    return new NextResponse(text, { status: upstream.status })
  }
}

