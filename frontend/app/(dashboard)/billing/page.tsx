import { auth } from "@/lib/auth"
import { db } from "@/lib/db"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Check, ExternalLink } from "lucide-react"

export default async function BillingPage() {
  const session = await auth()
  const customerId = (session?.user as any)?.customerId

  if (!customerId) return null

  const customer = await db.customer.findUnique({
    where: { id: customerId },
  })

  const isActive = customer?.status === "active"

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Billing</h1>
        <p className="text-muted-foreground">Manage your subscription</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Current Plan</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xl font-bold">$29/mo</span>
                <Badge variant={isActive ? "default" : "secondary"}>
                  {isActive ? "Active" : customer?.status ?? "Inactive"}
                </Badge>
              </div>
              <p className="text-sm text-muted-foreground">
                AI Receptionist — Full access
              </p>
            </div>
            <form action="/api/stripe/checkout" method="POST">
              <input type="hidden" name="customerId" value={customerId} />
              <Button type="submit" variant="outline" disabled={!isActive}>
                <ExternalLink className="h-4 w-4 mr-2" />
                Manage Subscription
              </Button>
            </form>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>What&apos;s Included</CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="space-y-2">
            {[
              "Dedicated phone number",
              "24/7 AI call answering",
              "Appointment scheduling",
              "Message taking + SMS delivery",
              "Call transcripts & summaries",
              "Custom FAQs & greetings",
              "Business hours configuration",
            ].map((item) => (
              <li key={item} className="flex items-center gap-2 text-sm">
                <Check className="h-4 w-4 text-primary" />
                {item}
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>

      {customer?.stripeCustomerId && (
        <p className="text-xs text-muted-foreground text-center">
          Stripe Customer: {customer.stripeCustomerId}
        </p>
      )}
    </div>
  )
}
