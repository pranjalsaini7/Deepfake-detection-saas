import { Inter } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/components/AuthProvider";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700", "800", "900"],
});

export const metadata = {
  title: "VERITAS | Precision in Truth",
  description:
    "Advanced digital forensics powered by deep ensemble networks. Detect synthetic manipulation with clinical precision and sub-second inference.",
  keywords: "deepfake detection, AI, Grad-CAM, EfficientNet, face forensics, SaaS",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en" className={inter.variable}>
      <body>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
