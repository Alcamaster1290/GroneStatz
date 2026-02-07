"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function HomeAutoRedirect() {
  const router = useRouter();

  useEffect(() => {
    const token = localStorage.getItem("fantasy_token");
    if (token) {
      router.replace("/team");
    }
  }, [router]);

  return null;
}
