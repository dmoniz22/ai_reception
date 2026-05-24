import { NextRequest, NextResponse } from "next/server"
import bcrypt from "bcryptjs"
import { db } from "@/lib/db"

export async function POST(req: NextRequest) {
  const { email, password, businessName, ownerName } = await req.json()

  if (!email || !password || !businessName) {
    return NextResponse.json({ error: "Missing required fields" }, { status: 400 })
  }

  const existing = await db.user.findUnique({ where: { email } })
  if (existing) {
    return NextResponse.json({ error: "Email already registered" }, { status: 409 })
  }

  const passwordHash = await bcrypt.hash(password, 12)

  const user = await db.user.create({
    data: { email, passwordHash },
  })

  const customer = await db.customer.create({
    data: {
      businessName,
      ownerName: ownerName || null,
      email,
    },
  })

  await db.user.update({
    where: { id: user.id },
    data: { customerId: customer.id },
  })

  return NextResponse.json({
    userId: user.id,
    customerId: customer.id,
  })
}
