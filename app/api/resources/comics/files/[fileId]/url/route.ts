import { NextResponse } from "next/server"
import { cookies } from "next/headers"
import { adminFetch } from "@/lib/admin-api"

export async function GET(
  request: Request,
  context: { params: Promise<{ fileId: string }> }
) {
  const params = await context.params
  const cookieStore = await cookies()
  const token = cookieStore.get("admin_token")?.value
  if (!token) {
    return NextResponse.json({ message: "Unauthorized" }, { status: 401 })
  }

  const upstream = await adminFetch(`/resources/comics/files/${params.fileId}/url`, undefined, token)
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

