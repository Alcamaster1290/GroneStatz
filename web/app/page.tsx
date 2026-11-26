import { redirect } from "next/navigation";
import { getJson } from "@/lib/api";
import type { SeasonInfo } from "@/lib/types";

/** La portada es la liga de la última temporada, en su torneo más reciente. */
export default async function Home() {
  const { seasons } = await getJson<{ seasons: SeasonInfo[] }>("/v1/seasons");
  const latest = seasons[0];
  const tournament = latest.tournaments.includes("Clausura") ? "Clausura" : latest.tournaments[0];
  redirect(`/liga/${latest.season}/${tournament}`);
}
