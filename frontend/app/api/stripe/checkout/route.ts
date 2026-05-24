import { NextRequest, NextResponse } from "next/server"
import { stripe } from "@/lib/stripe"
import { db } from "@/lib/db"

export async function POST(req: NextRequest) {
  const { customerId } = await req.json()

  const customer = await db.customer.findUnique({
    where: { id: customerId },
  })

  if (!customer) {
    return NextResponse.json({ error: "Customer not found" }, { status: 404 })
  }

  let stripeCustomerId = customer.stripeCustomerId

  if (!stripeCustomerId) {
    const sc = await stripe.customers.create({
      email: customer.email,
      metadata: { customerId: customer.id },
    })
    stripeCustomerId = sc.id
    await db.customer.update({
      where: { id: customer.id },
      data: { stripeCustomerId: sc.id },
    })
  }

  const session = await stripe.checkout.sessions.create({
    customer: stripeCustomerId,
    payment_method_types: ["card"],
    mode: "subscription",
    line_items: [
      {
        price: process.env.STRIPE_PRICE_ID!,
        quantity: 1,
      },
    ],
    success_url: `${req.nextUrl.origin}/dashboard?checkout=success`,
    cancel_url: `${req.nextUrl.origin}/pricing?checkout=cancelled`,
  })

  return NextResponse.json({ url: session.url })
}
