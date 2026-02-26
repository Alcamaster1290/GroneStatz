import { redirect } from "next/navigation";

// Keep "/" dynamic and always send to landing.
export const dynamic = "force-dynamic";
export const revalidate = 0;

export default function Home() {
  redirect("/landing");
}
