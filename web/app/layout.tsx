import type { Metadata } from "next";
import { Poppins } from "next/font/google";
import { cookies } from "next/headers";
import Navigation from "@/components/ui/navigation";
import { SESSION_COOKIE, isAuthEnabled, verifySessionValue } from "@/lib/auth";
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

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const authEnabled = isAuthEnabled();
  const loggedIn = authEnabled
    ? await verifySessionValue((await cookies()).get(SESSION_COOKIE)?.value)
    : true;

  return (
    <html lang="en">
      <body className={`${poppins.className} min-h-screen bg-black`}>
        <Navigation authEnabled={authEnabled} loggedIn={loggedIn} />
        <main className="pt-16">{children}</main>
      </body>
    </html>
  );
}
