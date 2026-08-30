import { redirect } from "next/navigation";

export default function Home() {
  // The dashboard route guard sends unauthenticated visitors on to /login.
  redirect("/dashboard");
}
