import "./globals.css";

export const metadata = {
  title: "Personal Agent",
  description: "Next.js frontend for the Personal Agent workspace",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
