import { auth } from "@/lib/auth"
import { db } from "@/lib/db"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { formatDateTime, formatDuration, formatPhone } from "@/lib/utils"
import { Eye } from "lucide-react"

export default async function CallsPage() {
  const session = await auth()
  const customerId = (session?.user as any)?.customerId

  if (!customerId) return null

  const calls = await db.callLog.findMany({
    where: { customerId },
    orderBy: { startedAt: "desc" },
    take: 100,
  })

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Call Log</h1>
        <p className="text-muted-foreground">History of all calls answered by your AI receptionist</p>
      </div>

      <Card>
        <CardContent className="p-0">
          {calls.length === 0 ? (
            <div className="py-12 text-center text-muted-foreground">
              No calls yet
            </div>
          ) : (
            <div className="hidden md:block">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Caller</TableHead>
                    <TableHead>Date</TableHead>
                    <TableHead>Duration</TableHead>
                    <TableHead>Outcome</TableHead>
                    <TableHead className="w-20"></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {calls.map((call) => (
                    <TableRow key={call.id}>
                      <TableCell className="font-mono text-sm">
                        {formatPhone(call.callerNumber)}
                      </TableCell>
                      <TableCell className="text-sm">
                        {call.startedAt ? formatDateTime(call.startedAt) : "—"}
                      </TableCell>
                      <TableCell className="text-sm">
                        {call.durationSeconds ? formatDuration(call.durationSeconds) : "—"}
                      </TableCell>
                      <TableCell>
                        <Badge variant="secondary" className="text-xs">
                          {call.outcome ?? "completed"}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Dialog>
                          <DialogTrigger>
                            <Button variant="ghost" size="icon">
                              <Eye className="h-4 w-4" />
                            </Button>
                          </DialogTrigger>
                          <DialogContent className="max-w-lg">
                            <DialogHeader>
                              <DialogTitle>Call Details</DialogTitle>
                            </DialogHeader>
                            <div className="space-y-3 text-sm">
                              <div>
                                <span className="text-muted-foreground">Caller: </span>
                                {formatPhone(call.callerNumber)}
                              </div>
                              <div>
                                <span className="text-muted-foreground">Date: </span>
                                {call.startedAt ? formatDateTime(call.startedAt) : "—"}
                              </div>
                              <div>
                                <span className="text-muted-foreground">Duration: </span>
                                {call.durationSeconds ? formatDuration(call.durationSeconds) : "—"}
                              </div>
                              <div>
                                <span className="text-muted-foreground">Outcome: </span>
                                <Badge variant="secondary" className="text-xs">
                                  {call.outcome ?? "completed"}
                                </Badge>
                              </div>
                              {call.summary && (
                                <div className="pt-2 border-t">
                                  <p className="text-muted-foreground mb-1">Summary:</p>
                                  <p>{call.summary}</p>
                                </div>
                              )}
                            </div>
                          </DialogContent>
                        </Dialog>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}

          <div className="md:hidden divide-y">
            {calls.map((call) => (
              <div key={call.id} className="p-4 space-y-2">
                <div className="flex justify-between items-start">
                  <div>
                    <p className="font-mono text-sm font-medium">
                      {formatPhone(call.callerNumber)}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {call.startedAt ? formatDateTime(call.startedAt) : "—"}
                    </p>
                  </div>
                  <Badge variant="secondary" className="text-xs">
                    {call.outcome ?? "completed"}
                  </Badge>
                </div>
                {call.summary && (
                  <p className="text-xs text-muted-foreground line-clamp-2">
                    {call.summary}
                  </p>
                )}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
