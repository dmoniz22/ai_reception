import { Card, CardContent } from "@/components/ui/card"
import { Clock, CalendarCheck, MessageSquare, Bell } from "lucide-react"

const features = [
  {
    icon: Clock,
    title: "24/7 Call Answering",
    description: "Never miss a call again. Your AI receptionist answers every call, day or night, weekends and holidays.",
  },
  {
    icon: CalendarCheck,
    title: "Appointment Scheduling",
    description: "Callers can book appointments directly on your calendar. The AI checks availability and confirms bookings in real-time.",
  },
  {
    icon: MessageSquare,
    title: "Message Taking",
    description: "When you can't take a call, the AI takes a detailed message and sends it to you instantly via SMS.",
  },
  {
    icon: Bell,
    title: "Smart Call Summaries",
    description: "After every call, get an AI-generated summary delivered to your phone so you always know what's happening.",
  },
]

export function Features() {
  return (
    <section id="features" className="container mx-auto px-4 py-16 md:py-24">
      <div className="text-center mb-12">
        <h2 className="text-3xl font-bold tracking-tight">
          Everything Your Front Desk Needs
        </h2>
        <p className="mt-4 text-lg text-muted-foreground max-w-2xl mx-auto">
          Powered by AI, designed for small businesses. No hardware, no setup fees, no contracts.
        </p>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {features.map((f) => (
          <Card key={f.title} className="border-0 shadow-none bg-muted/50">
            <CardContent className="pt-6">
              <f.icon className="h-10 w-10 text-primary mb-4" />
              <h3 className="font-semibold text-lg mb-2">{f.title}</h3>
              <p className="text-sm text-muted-foreground">{f.description}</p>
            </CardContent>
          </Card>
        ))}
      </div>
    </section>
  )
}
