import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Check } from "lucide-react"
import Link from "next/link"

export function PricingSection() {
  return (
    <section className="container mx-auto px-4 py-16 md:py-24">
      <div className="text-center mb-12">
        <h2 className="text-3xl font-bold tracking-tight">
          Simple, Transparent Pricing
        </h2>
        <p className="mt-4 text-lg text-muted-foreground">
          One plan, everything included. No hidden fees.
        </p>
      </div>
      <div className="max-w-md mx-auto">
        <div className="border rounded-2xl p-8 text-center relative">
          <Badge className="absolute -top-3 left-1/2 -translate-x-1/2">
            Free 30-Day Trial
          </Badge>
          <p className="text-sm text-muted-foreground mt-4 mb-2">Monthly Plan</p>
          <div className="flex items-baseline justify-center gap-1 mb-6">
            <span className="text-5xl font-bold">$29</span>
            <span className="text-muted-foreground">/mo</span>
          </div>
          <ul className="space-y-3 text-left mb-8">
            {[
              "Dedicated phone number",
              "24/7 AI call answering",
              "Appointment scheduling",
              "Message taking + SMS delivery",
              "Call transcripts & summaries",
              "Custom FAQs & greetings",
              "Business hours configuration",
            ].map((item) => (
              <li key={item} className="flex items-start gap-2 text-sm">
                <Check className="h-4 w-4 text-primary mt-0.5 shrink-0" />
                {item}
              </li>
            ))}
          </ul>
          <Button size="lg" className="w-full" render={<Link href="/signup" />}>
            Start Free Trial
          </Button>
        </div>
      </div>
    </section>
  )
}
