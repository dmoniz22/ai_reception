const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001"

async function fetchAPI(path: string, options: RequestInit = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  })

  if (!res.ok) {
    const error = await res.text()
    throw new Error(error || `API error: ${res.status}`)
  }

  return res.json()
}

export interface CustomerData {
  id: string
  business_name: string
  owner_name: string | null
  email: string
  phone: string | null
  timezone: string
  twilio_phone_number: string | null
  deepgram_agent_id: string | null
  business_hours: Record<string, string> | null
  faqs: Array<{ q: string; a: string }> | null
  greeting: string | null
  calendar_integration: string | null
  stripe_customer_id: string | null
  stripe_subscription_id: string | null
  status: string
  created_at: string
}

export interface CallLogData {
  id: string
  caller_number: string
  call_sid: string | null
  started_at: string | null
  ended_at: string | null
  duration_seconds: number | null
  outcome: string | null
  summary: string | null
}

export const api = {
  getCustomer: (id: string) => fetchAPI(`/api/customers/${id}`) as Promise<CustomerData>,
  updateCustomer: (id: string, data: Partial<CustomerData>) =>
    fetchAPI(`/api/customers/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }) as Promise<CustomerData>,
  getCustomerCalls: (id: string) =>
    fetchAPI(`/api/customers/${id}/calls`) as Promise<CallLogData[]>,
  createCustomer: (data: Record<string, unknown>) =>
    fetchAPI("/api/customers", {
      method: "POST",
      body: JSON.stringify(data),
    }) as Promise<CustomerData>,
  getOAuthUrl: (customerId: string) =>
    fetchAPI(`/api/scheduling/oauth/authorize?customer_id=${customerId}`) as Promise<{ url?: string }>,
}
