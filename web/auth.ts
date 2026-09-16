import NextAuth from "next-auth"
import Keycloak from "next-auth/providers/keycloak"

const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH ?? ""
const CLIENT_ID = process.env.KEYCLOAK_CLIENT_ID ?? "secretshare-api"
const CLIENT_SECRET = process.env.KEYCLOAK_CLIENT_SECRET ?? ""

export const { handlers, signIn, signOut, auth } = NextAuth((req) => {
  const host = req?.headers.get("x-forwarded-host") || req?.headers.get("host") || "localhost"
  const proto = req?.headers.get("x-forwarded-proto") || "http"
  const origin = `${proto}://${host}`
  const issuer =
    process.env.KEYCLOAK_ISSUER ||
    `${origin}${BASE_PATH ? BASE_PATH : ""}/keycloak/realms/secretshare`

  return {
    basePath: `${BASE_PATH}/api/auth`,
    trustHost: true,
    providers: [
      Keycloak({
        clientId: CLIENT_ID,
        clientSecret: CLIENT_SECRET,
        issuer,
      }),
    ],
    callbacks: {
      async jwt({ token, account, profile }) {
        if (account) {
          token.accessToken = account.access_token
          token.idToken = account.id_token
        }
        if (profile) {
          token.username = (profile as any).preferred_username ?? (profile as any).sub
        }
        return token
      },
      async session({ session, token }) {
        if (token) {
          session.accessToken = token.accessToken as string
          if (token.username && session.user) {
            session.user.name = token.username as string
          }
        }
        return session
      },
    },
  }
})
