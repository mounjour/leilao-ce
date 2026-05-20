import Stripe from "npm:stripe@14";
import { createClient } from "npm:@supabase/supabase-js@2";

const stripe = new Stripe(Deno.env.get("STRIPE_SECRET_KEY")!);

const supabase = createClient(
  Deno.env.get("SUPABASE_URL")!,
  Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!
);

Deno.serve(async (req) => {
  const signature = req.headers.get("stripe-signature");
  const body = await req.text();

  let event: Stripe.Event;
  try {
    event = stripe.webhooks.constructEvent(
      body,
      signature!,
      Deno.env.get("STRIPE_WEBHOOK_SECRET")!
    );
  } catch (err) {
    console.error("Webhook signature invalid:", err.message);
    return new Response(`Webhook Error: ${err.message}`, { status: 400 });
  }

  console.log("Event received:", event.type);

  switch (event.type) {
    case "checkout.session.completed": {
      const session = event.data.object as Stripe.Checkout.Session;
      const email =
        session.customer_email ??
        (session.metadata?.supabase_user_email as string);
      const customerId = session.customer as string;
      const subscriptionId = session.subscription as string;

      if (email) {
        const { error } = await supabase
          .from("profiles")
          .update({
            subscription_status: "active",
            stripe_customer_id: customerId,
            stripe_subscription_id: subscriptionId,
            updated_at: new Date().toISOString(),
          })
          .eq("email", email);

        if (error) console.error("Error activating subscription:", error);
        else console.log("Subscription activated for:", email);
      }
      break;
    }

    case "customer.subscription.deleted": {
      const sub = event.data.object as Stripe.Subscription;
      const { error } = await supabase
        .from("profiles")
        .update({
          subscription_status: "inactive",
          updated_at: new Date().toISOString(),
        })
        .eq("stripe_customer_id", sub.customer as string);

      if (error) console.error("Error deactivating subscription:", error);
      break;
    }

    case "invoice.payment_failed": {
      const invoice = event.data.object as Stripe.Invoice;
      const { error } = await supabase
        .from("profiles")
        .update({
          subscription_status: "inactive",
          updated_at: new Date().toISOString(),
        })
        .eq("stripe_customer_id", invoice.customer as string);

      if (error) console.error("Error on payment failed:", error);
      break;
    }
  }

  return new Response(JSON.stringify({ received: true }), {
    headers: { "Content-Type": "application/json" },
  });
});
