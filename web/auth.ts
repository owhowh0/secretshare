import NextAuth from "next-auth"
import Keycloak from "next-auth/providers/keycloak"

export const { handlers, signIn, signOut, auth } = NextAuth({
  providers: [
    Keycloak({
      clientId:
        process.env.AUTH_KEYCLOAK_ID ??
        process.env.KEYCLOAK_CLIENT_ID ??
        "secretshare-api",
      clientSecret:
        process.env.AUTH_KEYCLOAK_SECRET ??
        process.env.KEYCLOAK_CLIENT_SECRET ??
        "",
      issuer:
        process.env.AUTH_KEYCLOAK_ISSUER ??
        process.env.KEYCLOAK_ISSUER,
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
})
