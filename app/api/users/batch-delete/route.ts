import { cookies } from "next/headers"
import { NextResponse } from "next/server"
import { adminFetch } from "@/lib/admin-api"

export async function POST(request: Request) {
  try {
    const cookieStore = await cookies()
    const token = cookieStore.get("admin_token")?.value
    if (!token) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
    }

    const body = await request.json()
    await adminFetch(
      "/users/batch-delete",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      },
      token,
    )
    return new NextResponse(null, { status: 204 })
  } catch (error) {
    console.error("Failed to batch delete users:", error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Failed to batch delete users" },
      { status: 500 }
    )
  }
}

