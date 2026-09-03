import Stripe from "npm:stripe@^22";
import { createClient } from "npm:@supabase/supabase-js@2";

const stripeSecret = Deno.env.get("STRIPE_SECRET_KEY") ?? "";
const webhookSecret = Deno.env.get("STRIPE_WEBHOOK_SECRET") ?? "";
const supabaseUrl = Deno.env.get("SUPABASE_URL") ?? "";
const serviceRoleKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";

if (!stripeSecret || !webhookSecret || !supabaseUrl || !serviceRoleKey) {
  throw new Error("Secrets obrigatórios da cobrança não foram configurados.");
}

const stripe = new Stripe(stripeSecret);
const cryptoProvider = Stripe.createSubtleCryptoProvider();
const supabase = createClient(supabaseUrl, serviceRoleKey, {
  auth: { persistSession: false, autoRefreshToken: false },
});

type ProfileUpdate = {
  subscription_status?: string;
  stripe_customer_id?: string | null;
  stripe_subscription_id?: string | null;
  subscription_current_period_end?: string | null;
  updated_at: string;
};

const objectId = (value: unknown): string | null => {
  if (typeof value === "string") return value;
  if (value && typeof value === "object" && "id" in value) {
    return String((value as { id: unknown }).id);
  }
  return null;
};

const isoFromUnix = (value: unknown): string | null => {
  const seconds = Number(value);
  return Number.isFinite(seconds) && seconds > 0
    ? new Date(seconds * 1000).toISOString()
    : null;
};

type AuthContact = {
  email?: string | null;
  phone?: string;
  name?: string;
  full_name?: string;
};

// Le phone/name/full_name/email de auth.users.raw_user_meta_data via admin API.
// Usado so no fallback de emergencia, quando o trigger handle_new_user nao
// gravou a linha em public.profiles e alertas.py ficaria sem telefone.
async function authUserContact(userId: string): Promise<AuthContact> {
  try {
    const { data, error } = await supabase.auth.admin.getUserById(userId);
    if (error || !data?.user) return {};
    const meta = (data.user.user_metadata ?? {}) as Record<string, unknown>;
    const pick = (key: string): string | undefined => {
      const value = meta[key];
      return typeof value === "string" && value.trim() ? value.trim() : undefined;
    };
    return {
      email: data.user.email ?? null,
      phone: pick("phone"),
      name: pick("name"),
      full_name: pick("full_name"),
    };
  } catch (error) {
    console.error("Falha ao ler auth.users no fallback do webhook", userId, error);
    return {};
  }
}

async function updateProfile(
  values: ProfileUpdate,
  identity: { userId?: string | null; customerId?: string | null; email?: string | null },
) {
  const candidates: Array<[string, string | null | undefined]> = [
    ["id", identity.userId],
    ["stripe_customer_id", identity.customerId],
    ["email", identity.email],
  ];

  for (const [column, value] of candidates) {
    if (!value) continue;
    const { data, error } = await supabase
      .from("profiles")
      .update(values)
      .eq(column, value)
      .select("id")
      .limit(1);
    if (error) throw error;
    if (data?.length) return;
  }

  // Nenhuma linha bateu. Se conhecemos o id do usuario (a PK de profiles),
  // cria/atualiza a linha via upsert — cobre o caso raro de o trigger
  // handle_new_user nao ter rodado no signup. Sem o id nao da pra inserir
  // com seguranca (customerId/email nao sao a PK).
  if (identity.userId) {
    // O trigger perdeu o signup: puxa contato de auth.users para a linha
    // nao nascer sem phone/name (senao alertas.py nunca manda WhatsApp).
    const contact = await authUserContact(identity.userId);
    const row: Record<string, unknown> = {
      id: identity.userId,
      email: identity.email ?? contact.email ?? null,
      ...values,
    };
    // So grava contato quando temos valor — nunca sobrescreve com null.
    if (contact.phone) row.phone = contact.phone;
    if (contact.name) row.name = contact.name;
    if (contact.full_name) row.full_name = contact.full_name;

    const { error } = await supabase
      .from("profiles")
      .upsert(row, { onConflict: "id" });
    if (error) throw error;
    return;
  }

  throw new Error("Nenhum perfil corresponde à identidade do evento Stripe.");
}

async function syncSubscription(subscription: Stripe.Subscription) {
  const raw = subscription as unknown as Record<string, unknown>;
  const customerId = objectId(subscription.customer);
  const userId = subscription.metadata?.supabase_user_id || null;
  const periodEnd =
    raw.current_period_end ??
    (raw.items as { data?: Array<Record<string, unknown>> } | undefined)
      ?.data?.[0]?.current_period_end;

  await updateProfile(
    {
      subscription_status: subscription.status,
      stripe_customer_id: customerId,
      stripe_subscription_id: subscription.id,
      subscription_current_period_end: isoFromUnix(periodEnd),
      updated_at: new Date().toISOString(),
    },
    { userId, customerId },
  );
}

async function subscriptionFromInvoice(invoice: Stripe.Invoice) {
  const raw = invoice as unknown as Record<string, any>;
  const subscriptionId = objectId(
    raw.subscription ?? raw.parent?.subscription_details?.subscription,
  );
  if (!subscriptionId) return null;
  return await stripe.subscriptions.retrieve(subscriptionId);
}

Deno.serve(async (req: Request) => {
  if (req.method !== "POST") {
    return new Response("Method Not Allowed", { status: 405 });
  }

  const signature = req.headers.get("stripe-signature");
  if (!signature) return new Response("Assinatura Stripe ausente.", { status: 400 });

  const rawBody = await req.text();
  let event: Stripe.Event;
  try {
    event = await stripe.webhooks.constructEventAsync(
      rawBody,
      signature,
      webhookSecret,
      undefined,
      cryptoProvider,
    );
  } catch (error) {
    const message = error instanceof Error ? error.message : "assinatura inválida";
    console.error("Webhook Stripe rejeitado:", message);
    return new Response(`Webhook Error: ${message}`, { status: 400 });
  }

  try {
    const { data: processed } = await supabase
      .from("billing_webhook_events")
      .select("event_id")
      .eq("event_id", event.id)
      .maybeSingle();
    if (processed) return Response.json({ received: true, duplicate: true });

    switch (event.type) {
      case "checkout.session.completed": {
        const session = event.data.object as Stripe.Checkout.Session;
        const subscriptionId = objectId(session.subscription);
        const customerId = objectId(session.customer);
        const userId =
          session.client_reference_id || session.metadata?.supabase_user_id || null;
        const email =
          session.customer_details?.email ||
          session.customer_email ||
          session.metadata?.supabase_user_email ||
          null;

        if (subscriptionId) {
          const subscription = await stripe.subscriptions.retrieve(subscriptionId);
          await updateProfile(
            {
              subscription_status: subscription.status,
              stripe_customer_id: customerId,
              stripe_subscription_id: subscription.id,
              subscription_current_period_end: isoFromUnix(
                (subscription as unknown as Record<string, unknown>).current_period_end,
              ),
              updated_at: new Date().toISOString(),
            },
            { userId, customerId, email },
          );
        }
        break;
      }

      case "customer.subscription.created":
      case "customer.subscription.updated":
      case "customer.subscription.deleted":
        await syncSubscription(event.data.object as Stripe.Subscription);
        break;

      case "invoice.paid":
      case "invoice.payment_failed": {
        const subscription = await subscriptionFromInvoice(
          event.data.object as Stripe.Invoice,
        );
        if (subscription) await syncSubscription(subscription);
        break;
      }
    }

    const { error: logError } = await supabase
      .from("billing_webhook_events")
      .insert({ event_id: event.id, event_type: event.type });
    if (logError && logError.code !== "23505") throw logError;

    return Response.json({ received: true });
  } catch (error) {
    console.error("Falha ao processar evento", event.id, event.type, error);
    return Response.json({ received: false }, { status: 500 });
  }
});
