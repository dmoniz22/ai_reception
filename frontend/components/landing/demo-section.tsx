import { Button } from "@/components/ui/button"
import { Phone } from "lucide-react"

export function DemoSection() {
  return (
    <section id="demo" className="container mx-auto px-4 py-16 md:py-24">
      <div className="max-w-2xl mx-auto text-center bg-muted/50 rounded-2xl p-8 md:p-12">
        <h2 className="text-3xl font-bold tracking-tight mb-4">
          Try It Yourself
        </h2>
        <p className="text-lg text-muted-foreground mb-8">
          Call our demo number and talk to an AI receptionist. Ask about hours, book an appointment, or leave a message.
        </p>
        <div className="inline-flex items-center gap-3 text-2xl font-mono font-bold text-primary mb-6">
          <Phone className="h-6 w-6" />
          (604) 555-0199
        </div>
        <p className="text-sm text-muted-foreground mb-8">
          Demo number available 24/7. Standard call rates may apply.
        </p>
        <Button variant="outline" size="lg" render={<a href="tel:+16045551999" />}>
          Call Now
        </Button>
      </div>
    </section>
  )
}
