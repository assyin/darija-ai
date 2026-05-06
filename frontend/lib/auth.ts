import NextAuth, { type NextAuthConfig } from "next-auth";
import Credentials from "next-auth/providers/credentials";

const isDev = process.env.NODE_ENV !== "production";
const adminEmail = process.env.ADMIN_EMAIL || "admin@darija-ai.local";

export const authConfig: NextAuthConfig = {
  pages: { signIn: "/login" },
  session: { strategy: "jwt" },
  providers: [
    // TEMPORARY DEV PROVIDER — auto-login for development only.
    // Replace with the Resend magic-link provider when RESEND_API_KEY is set.
    Credentials({
      id: "dev-bypass",
      name: "Dev Auto-Login",
      credentials: {},
      async authorize() {
        if (!isDev) return null;
        return {
          id: "dev-admin",
          email: adminEmail,
          name: "Admin (DEV)",
        };
      },
    }),
    // FUTURE — uncomment when Resend is configured:
    // Resend({
    //   apiKey: process.env.RESEND_API_KEY,
    //   from: "noreply@darija-ai.com",
    // }),
  ],
  callbacks: {
    authorized({ auth, request: { nextUrl } }) {
      const isAdminRoute = nextUrl.pathname.startsWith("/admin");
      if (!isAdminRoute) return true;
      return !!auth?.user;
    },
  },
};

export const { handlers, signIn, signOut, auth } = NextAuth(authConfig);
