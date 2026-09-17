import { handlers } from "@/auth"
import { NextRequest } from "next/server"

const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH ?? ""

function sanitizeRequest(req: NextRequest): NextRequest {
  const url = new URL(req.url)
  if (BASE_PATH && !url.pathname.startsWith(BASE_PATH)) {
    url.pathname = `${BASE_PATH}${url.pathname}`
  }
  if (url.pathname.endsWith("/") && url.pathname.length > 1) {
    url.pathname = url.pathname.replace(/\/+$/, "")
  }
  return new NextRequest(url, req)
}

export async function GET(req: NextRequest) {
  return handlers.GET(sanitizeRequest(req))
}

export async function POST(req: NextRequest) {
  return handlers.POST(sanitizeRequest(req))
}
