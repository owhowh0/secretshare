import { handlers } from "@/auth"
import { NextRequest } from "next/server"

function sanitizeRequest(req: NextRequest): NextRequest {
  const url = new URL(req.url)
  if (url.pathname.endsWith("/") && url.pathname.length > 1) {
    url.pathname = url.pathname.replace(/\/+$/, "")
    return new NextRequest(url, req)
  }
  return req
}

export async function GET(req: NextRequest) {
  return handlers.GET(sanitizeRequest(req))
}

export async function POST(req: NextRequest) {
  return handlers.POST(sanitizeRequest(req))
}
