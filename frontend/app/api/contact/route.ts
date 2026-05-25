// MVP placeholder — logs the contact submission and returns 200.
// TODO: forward to admin_notification_email via Resend when configured.

export async function POST(req: Request) {
  try {
    const body = (await req.json()) as {
      name?: string;
      email?: string;
      message?: string;
    };
    if (!body.name || !body.email || !body.message) {
      return Response.json({ ok: false, error: "missing_fields" }, { status: 400 });
    }
    // eslint-disable-next-line no-console
    console.log("[Contact form]", body);
    return Response.json({ ok: true });
  } catch {
    return Response.json({ ok: false, error: "bad_request" }, { status: 400 });
  }
}
