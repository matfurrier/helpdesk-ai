import type { Metadata } from "next";
import "./globals.css";
import { QueryProviders } from "@/components/providers/query-providers";

export const metadata: Metadata = {
  title: "IT Helpdesk",
  description: "Internal IT support portal",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR" className="dark">
      <body>
        <QueryProviders>{children}</QueryProviders>
      </body>
    </html>
  );
}
