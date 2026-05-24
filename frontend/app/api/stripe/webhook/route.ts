import { NextRequest, NextResponse } from "next/server"
import { stripe } from "@/lib/stripe"
import { db } from "@/lib/db"

export async function POST(req: NextRequest) {
  const body = await req.text()
  const sig = req.headers.get("stripe-signature")!

  let event
  try {
    event = stripe.webhooks.constructEvent(
      body,
      sig,
      process.env.STRIPE_WEBHOOK_SECRET!,
    )
  } catch {
    return NextResponse.json({ error: "Invalid signature" }, { status: 400 })
  }

  if (event.type === "checkout.session.completed") {
    const session = event.data.object as any
    const stripeCustomerId = session.customer
    const subscriptionId = session.subscription as string

    await db.customer.updateMany({
      where: { stripeCustomerId },
      data: {
        stripeSubscriptionId: subscriptionId,
        status: "active",
      },
    })
  }

  if (event.type === "customer.subscription.deleted") {
    const sub = event.data.object as any
    await db.customer.updateMany({
      where: { stripeCustomerId: sub.customer as string },
      data: { status: "cancelled", stripeSubscriptionId: null },
    })
  }

  return NextResponse.json({ received: true })
}
