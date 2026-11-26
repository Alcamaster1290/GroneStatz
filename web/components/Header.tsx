import Link from "next/link";

export default function Header() {
  return (
    <header className="border-b border-line bg-surface">
      <div className="mx-auto flex w-full max-w-6xl items-center gap-6 px-4 py-3">
        <Link href="/" className="text-lg font-bold tracking-tight">
          Grone<span className="text-accent">Stats</span>
        </Link>
        <nav aria-label="Principal" className="flex gap-4 text-sm text-muted">
          <Link href="/" className="hover:text-ink">
            Liga
          </Link>
          <Link href="/estado" className="hover:text-ink">
            Estado de los datos
          </Link>
        </nav>
      </div>
    </header>
  );
}
