import { Suspense } from "react";

import LoginClient from "./LoginClient";

function LoginFallback() {
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-ink">Login</h1>
        <p className="text-sm text-muted">Accede para continuar al juego.</p>
      </div>
      <div className="glass rounded-2xl p-4 text-sm text-muted">Cargando...</div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<LoginFallback />}>
      <LoginClient />
    </Suspense>
  );
}
