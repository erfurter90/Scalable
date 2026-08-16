import { redirect } from "next/navigation";

export default function RootPage() {
  // proxy.ts gates this: with a session cookie present it forwards here, otherwise to /login.
  redirect("/dashboard");
}
