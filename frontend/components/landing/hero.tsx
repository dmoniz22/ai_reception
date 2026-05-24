import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Phone, ArrowRight } from "lucide-react"
import Link from "next/link"

export function Hero() {
  return (
    <section className="container mx-auto px-4 pt-20 pb-16 md:pt-32 md:pb-24 text-center">
      <Badge variant="secondary" className="mb-6">
        24/7 AI Phone Answering for Small Businesses
      </Badge>
      <h1 className="text-4xl md:text-6xl font-bold tracking-tight max-w-3xl mx-auto leading-tight">
        Never Miss Another Business Call
      </h1>
      <p className="mt-6 text-lg md:text-xl text-muted-foreground max-w-2xl mx-auto">
        An AI receptionist that answers calls, books appointments, takes messages, and only transfers what matters. Set up in 5 minutes.
      </p>
      <div className="mt-10 flex flex-col sm:flex-row gap-4 justify-center">
        <Button size="lg" className="gap-2" render={<Link href="/signup" />}>
          Get Your AI Receptionist <ArrowRight className="h-4 w-4" />
        </Button>
        <Button variant="outline" size="lg" className="gap-2" render={<a href="#demo" />}>
          <Phone className="h-4 w-4" /> Try the Demo
        </Button>
      </div>
      <p className="mt-4 text-sm text-muted-foreground">
        $29/mo. Free 30-day trial. No credit card required.
      </p>
    </section>
  )
}
