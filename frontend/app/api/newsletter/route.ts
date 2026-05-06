// MVP placeholder — logs the email and returns 200.
// TODO: integrate Resend (audience subscription) when RESEND_API_KEY is set.

export async function POST(req: Request) {
  try {
    const { email } = (await req.json()) as { email?: string };
    if (!email || !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) {
      return Response.json({ ok: false, error: "invalid_email" }, { status: 400 });
    }
    // eslint-disable-next-line no-console
    console.log("[Newsletter signup]", email);
    return Response.json({ ok: true });
  } catch {
    return Response.json({ ok: false, error: "bad_request" }, { status: 400 });
  }
}
