import Link from "next/link"

export function Footer() {
  return (
    <footer className="border-t py-8">
      <div className="container mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-4 text-sm text-muted-foreground">
        <p>&copy; {new Date().getFullYear()} AI Receptionist. All rights reserved.</p>
        <div className="flex gap-6">
          <Link href="/pricing" className="hover:text-foreground transition-colors">
            Pricing
          </Link>
          <Link href="mailto:support@monizhealth.com" className="hover:text-foreground transition-colors">
            Contact
          </Link>
          <Link href="/login" className="hover:text-foreground transition-colors">
            Log in
          </Link>
        </div>
      </div>
    </footer>
  )
}
