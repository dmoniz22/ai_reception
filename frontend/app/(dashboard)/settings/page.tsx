"use client"

import { useState, useEffect } from "react"
import { useSession } from "next-auth/react"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import { toast } from "sonner"
import type { CustomerData } from "@/lib/api-client"

const DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"] as const

export default function SettingsPage() {
  const { data: session } = useSession()
  const router = useRouter()
  const customerId = (session?.user as any)?.customerId

  const [customer, setCustomer] = useState<CustomerData | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  const [businessName, setBusinessName] = useState("")
  const [ownerPhone, setOwnerPhone] = useState("")
  const [timezone, setTimezone] = useState("America/Vancouver")
  const [hours, setHours] = useState<Record<string, string>>({})
  const [dayEnabled, setDayEnabled] = useState<Record<string, boolean>>({})
  const [greeting, setGreeting] = useState("")
  const [faqs, setFaqs] = useState<Array<{ q: string; a: string }>>([])

  useEffect(() => {
    if (!customerId) return
    fetchData()
  }, [customerId])

  async function fetchData() {
    const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || ""}/api/customers/${customerId}`)
    const data = await res.json()
    setCustomer(data)
    setBusinessName(data.business_name ?? "")
    setOwnerPhone(data.phone ?? "")
    setTimezone(data.timezone ?? "America/Vancouver")
    setGreeting(data.greeting ?? "")
    setFaqs(data.faqs ?? [{ q: "", a: "" }])

    const h: Record<string, string> = {}
    const e: Record<string, boolean> = {}
    for (const d of DAYS) {
      h[d] = data.business_hours?.[d] ?? "9-5"
      e[d] = true
    }
    if (data.business_hours) {
      for (const d of DAYS) {
        e[d] = d in (data.business_hours ?? {})
        h[d] = data.business_hours?.[d] ?? "9-5"
      }
    }
    setHours(h)
    setDayEnabled(e)
    setLoading(false)
  }

  async function handleSave() {
    setSaving(true)
    const businessHours: Record<string, string> = {}
    for (const d of DAYS) {
      if (dayEnabled[d]) businessHours[d] = hours[d]
    }

    const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || ""}/api/customers/${customerId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        business_name: businessName,
        phone: ownerPhone,
        timezone,
        business_hours: businessHours,
        greeting,
        faqs: faqs.filter((f) => f.q && f.a),
      }),
    })

    if (res.ok) {
      toast.success("Settings saved")
      router.refresh()
    } else {
      toast.error("Failed to save settings")
    }
    setSaving(false)
  }

  function updateFaq(idx: number, field: "q" | "a", value: string) {
    setFaqs((prev) => {
      const next = [...prev]
      next[idx] = { ...next[idx], [field]: value }
      return next
    })
  }

  function addFaq() {
    setFaqs((prev) => [...prev, { q: "", a: "" }])
  }

  function removeFaq(idx: number) {
    setFaqs((prev) => prev.filter((_, i) => i !== idx))
  }

  if (loading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-8 w-48 bg-muted rounded" />
        <div className="h-96 bg-muted rounded-lg" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Settings</h1>
          <p className="text-muted-foreground">Configure your AI receptionist</p>
        </div>
        <Button onClick={handleSave} disabled={saving}>
          {saving ? "Saving..." : "Save Changes"}
        </Button>
      </div>

      <Tabs defaultValue="business" className="space-y-4">
        <TabsList>
          <TabsTrigger value="business">Business Info</TabsTrigger>
          <TabsTrigger value="hours">Hours</TabsTrigger>
          <TabsTrigger value="faqs">FAQs</TabsTrigger>
          <TabsTrigger value="greeting">Greeting</TabsTrigger>
        </TabsList>

        <TabsContent value="business">
          <Card>
            <CardHeader>
              <CardTitle>Business Information</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label>Business Name</Label>
                <Input
                  value={businessName}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => setBusinessName(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label>Your Phone (for SMS alerts)</Label>
                <Input
                  value={ownerPhone}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => setOwnerPhone(e.target.value)}
                  placeholder="+16045551234"
                />
              </div>
              <div className="space-y-2">
                <Label>Timezone</Label>
                <Input
                  value={timezone}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => setTimezone(e.target.value)}
                />
              </div>
              {customer?.twilio_phone_number && (
                <div className="space-y-2">
                  <Label>Your AI Number</Label>
                  <p className="text-lg font-mono text-primary">
                    {customer.twilio_phone_number}
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="hours">
          <Card>
            <CardHeader>
              <CardTitle>Business Hours</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {DAYS.map((day) => (
                <div key={day} className="flex items-center gap-4">
                  <Switch
                    checked={dayEnabled[day]}
                    onCheckedChange={(v: boolean) =>
                      setDayEnabled((prev) => ({ ...prev, [day]: v }))
                    }
                  />
                  <span className="w-10 font-medium capitalize">{day}</span>
                  <Input
                    className="w-32"
                    placeholder="9-5"
                    value={hours[day] ?? ""}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                      setHours((prev) => ({ ...prev, [day]: e.target.value }))
                    }
                    disabled={!dayEnabled[day]}
                  />
                  <span className="text-xs text-muted-foreground">
                    e.g. 9-5 or 8:30-16:30
                  </span>
                </div>
              ))}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="faqs">
          <Card>
            <CardHeader>
              <CardTitle>Frequently Asked Questions</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {faqs.map((faq, i) => (
                <div key={i} className="space-y-2 p-4 border rounded-lg relative">
                  <div className="space-y-1">
                    <Label>Question</Label>
                    <Input
                      value={faq.q}
                      onChange={(e: React.ChangeEvent<HTMLInputElement>) => updateFaq(i, "q", e.target.value)}
                      placeholder="What are your hours?"
                    />
                  </div>
                  <div className="space-y-1">
                    <Label>Answer</Label>
                    <Input
                      value={faq.a}
                      onChange={(e: React.ChangeEvent<HTMLInputElement>) => updateFaq(i, "a", e.target.value)}
                      placeholder="We're open Monday to Friday, 9am to 5pm."
                    />
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="absolute top-2 right-2 text-destructive"
                    onClick={() => removeFaq(i)}
                  >
                    Remove
                  </Button>
                </div>
              ))}
              <Button variant="outline" onClick={addFaq}>
                Add FAQ
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="greeting">
          <Card>
            <CardHeader>
              <CardTitle>Greeting Message</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label>Call Greeting</Label>
                <textarea
                  className="w-full min-h-24 rounded-md border bg-background px-3 py-2 text-sm"
                  value={greeting}
                  onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setGreeting(e.target.value)}
                  placeholder="Hello, thank you for calling {business_name}. How can I help you today?"
                />
                <p className="text-xs text-muted-foreground">
                  This is what callers hear when your AI receptionist answers. Use {"{business_name}"} as a placeholder.
                </p>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
