import { cookies } from "next/headers"
import { NextResponse } from "next/server"
import { adminFetch } from "@/lib/admin-api"

export async function GET(request: Request) {
  try {
    const cookieStore = await cookies()
    const token = cookieStore.get("admin_token")?.value
    if (!token) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
    }

    const { searchParams } = new URL(request.url)
    const search = searchParams.get("search")
    const skip = searchParams.get("skip") || "0"
    const limit = searchParams.get("limit") || "50"
    
    const params = new URLSearchParams()
    if (search) {
      params.append("search", search)
    }
    params.append("skip", skip)
    params.append("limit", limit)
    const query = params.toString() ? `?${params.toString()}` : ""
    
    const response = await adminFetch(`/users${query}`, undefined, token)
    const data = await response.json()
    return NextResponse.json(data)
  } catch (error) {
    console.error("Failed to fetch users:", error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Failed to fetch users" },
      { status: 500 }
    )
  }
}

export async function POST(request: Request) {
  try {
    const cookieStore = await cookies()
    const token = cookieStore.get("admin_token")?.value
    if (!token) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 })
    }

    const body = await request.json()
    const response = await adminFetch(
      "/users",
      {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      },
      token,
    )
    const data = await response.json()
    return NextResponse.json(data)
  } catch (error) {
    console.error("Failed to create user:", error)
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Failed to create user" },
      { status: 500 }
    )
  }
}

