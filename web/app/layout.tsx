import type { Metadata } from "next";
import { Poppins } from "next/font/google";
import Navigation from "@/components/ui/navigation";
import "./globals.css";

const poppins = Poppins({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Security Anomaly Explorer",
  description:
    "Upload web logs in NSS output format and see a human-readable timeline of events and anomalies.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={`${poppins.className} min-h-screen bg-black`}>
        <Navigation />
        <main className="pt-16">{children}</main>
      </body>
    </html>
  );
}
