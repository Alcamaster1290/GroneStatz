import Link from "next/link";

export default function NotFound() {
  return (
    <div className="py-16 text-center">
      <h1 className="text-2xl font-bold">No encontramos esa página</h1>
      <p className="mt-2 text-muted">El equipo, jugador o partido no existe en este release, o la temporada no tiene ese torneo.</p>
      <Link href="/" className="mt-6 inline-block rounded-full bg-accent px-4 py-2 text-sm font-semibold text-white">
        Volver a la liga
      </Link>
    </div>
  );
}
