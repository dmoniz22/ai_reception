import { Header } from "@/components/landing/header"
import { Hero } from "@/components/landing/hero"
import { Features } from "@/components/landing/features"
import { PricingSection } from "@/components/landing/pricing-section"
import { DemoSection } from "@/components/landing/demo-section"
import { Footer } from "@/components/landing/footer"

export default function HomePage() {
  return (
    <div className="flex flex-col min-h-screen">
      <Header />
      <main className="flex-1">
        <Hero />
        <Features />
        <DemoSection />
        <PricingSection />
      </main>
      <Footer />
    </div>
  )
}
