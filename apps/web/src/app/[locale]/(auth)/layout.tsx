import { GuestLayout } from "@/components/layout/GuestLayout";

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <GuestLayout>{children}</GuestLayout>;
}
