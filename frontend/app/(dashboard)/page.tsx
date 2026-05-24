import { auth } from "@/lib/auth"
import { db } from "@/lib/db"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { PhoneCall, CalendarCheck, MessageSquare, TrendingUp } from "lucide-react"
import { formatDateTime, formatDuration } from "@/lib/utils"

export default async function DashboardPage() {
  const session = await auth()
  const customerId = (session?.user as any)?.customerId

  if (!customerId) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-muted-foreground">No customer account linked. Please contact support.</p>
      </div>
    )
  }

  const [customer, callCount, messageCount, recentCalls] = await Promise.all([
    db.customer.findUnique({ where: { id: customerId } }),
    db.callLog.count({ where: { customerId } }),
    db.message.count({ where: { customerId } }),
    db.callLog.findMany({
      where: { customerId },
      orderBy: { startedAt: "desc" },
      take: 5,
    }),
  ])

  const stats = [
    { title: "Total Calls", value: String(callCount), icon: PhoneCall },
    { title: "Appointments", value: "Coming soon", icon: CalendarCheck },
    { title: "Messages", value: String(messageCount), icon: MessageSquare },
    { title: "Status", value: customer?.status ?? "active", icon: TrendingUp },
  ]

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">
          {customer?.businessName ?? "Dashboard"}
        </h1>
        <p className="text-muted-foreground">
          Your AI receptionist number:{" "}
          <span className="font-mono text-foreground">
            {customer?.twilioPhoneNumber ?? "Not provisioned yet"}
          </span>
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map((s) => (
          <Card key={s.title}>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                {s.title}
              </CardTitle>
              <s.icon className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold">{s.value}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Recent Calls</CardTitle>
        </CardHeader>
        <CardContent>
          {recentCalls.length === 0 ? (
            <p className="text-sm text-muted-foreground py-4 text-center">
              No calls yet. Your AI receptionist is ready to answer.
            </p>
          ) : (
            <div className="space-y-3">
              {recentCalls.map((call) => (
                <div
                  key={call.id}
                  className="flex items-center justify-between py-2 border-b last:border-0"
                >
                  <div>
                    <p className="text-sm font-medium">
                      {call.callerNumber}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {call.startedAt ? formatDateTime(call.startedAt) : "—"}
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    {call.durationSeconds && (
                      <span className="text-xs text-muted-foreground">
                        {formatDuration(call.durationSeconds)}
                      </span>
                    )}
                    <Badge variant="secondary" className="text-xs">
                      {call.outcome ?? "completed"}
                    </Badge>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
