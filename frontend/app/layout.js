import "./globals.css";

export const metadata = {
  title: "Personal Agent",
  description: "Next.js frontend for the Personal Agent workspace",
  icons: {
    icon: "/favicon.svg",
  },
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body suppressHydrationWarning>{children}</body>
    </html>
  );
}
