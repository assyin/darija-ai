import NextAuth, { type NextAuthConfig } from "next-auth";
import Credentials from "next-auth/providers/credentials";

// Server-side base URL for the backend API. NEXT_PUBLIC_* is fine here too —
// authorize() runs on the server during the credentials callback.
const API_BASE =
  process.env.API_BASE_URL ||
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  "http://localhost:8000/api/v1";

interface BackendToken {
  access_token: string;
  token_type: string;
  expires_in: number;
}

// 8 h. Must match `admin_jwt_expiry_seconds` in `backend/app/core/config.py`
// so the NextAuth session never outlives the backend JWT it carries — that's
// what caused the "0 articles after inactivity" bug: NextAuth thought the
// user was still logged in while the backend JWT had silently expired.
const ADMIN_SESSION_MAX_AGE_SECONDS = 8 * 60 * 60;

export const authConfig: NextAuthConfig = {
  pages: { signIn: "/login" },
  session: { strategy: "jwt", maxAge: ADMIN_SESSION_MAX_AGE_SECONDS },
  providers: [
    Credentials({
      id: "credentials",
      name: "Email + mot de passe",
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Mot de passe", type: "password" },
      },
      async authorize(credentials) {
        const email = credentials?.email;
        const password = credentials?.password;
        if (typeof email !== "string" || typeof password !== "string") {
          return null;
        }

        const res = await fetch(`${API_BASE}/auth/token`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, password }),
          cache: "no-store",
        });
        if (!res.ok) return null;

        const token = (await res.json()) as BackendToken;
        return {
          id: email,
          email,
          name: "Admin",
          accessToken: token.access_token,
          accessTokenExpires: Date.now() + token.expires_in * 1000,
        };
      },
    }),
  ],
  callbacks: {
    authorized({ auth, request: { nextUrl } }) {
      const isAdminRoute = nextUrl.pathname.startsWith("/admin");
      if (!isAdminRoute) return true;
      return !!auth?.user;
    },
    jwt({ token, user }) {
      // On sign-in, persist the backend JWT (and its expiry) into the NextAuth
      // session token, which is stored in an httpOnly cookie (decision D2).
      if (user) {
        token.accessToken = user.accessToken;
        token.accessTokenExpires = user.accessTokenExpires;
      }
      return token;
    },
    session({ session, token }) {
      session.accessToken = token.accessToken;
      session.accessTokenExpires = token.accessTokenExpires;
      return session;
    },
  },
};

export const { handlers, signIn, signOut, auth } = NextAuth(authConfig);
