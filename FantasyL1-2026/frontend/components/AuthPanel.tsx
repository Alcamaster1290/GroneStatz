"use client";

import { useState } from "react";

import { login, register } from "@/lib/api";
import { useFantasyStore } from "@/lib/store";

export default function AuthPanel() {
  const setToken = useFantasyStore((state) => state.setToken);
  const setUserEmail = useFantasyStore((state) => state.setUserEmail);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<string[]>([]);

  const mapAuthErrors = (raw: string): string[] => {
    const cleaned = raw.replace(/^Error:\s*/i, "");
    const parts = cleaned.split(/[|,]/).map((part) => part.trim()).filter(Boolean);
    const codes = parts.length ? parts : [cleaned];

    const dictionary: Record<string, string> = {
      email_invalid: "El correo no es válido.",
      password_min_length: "La contraseña debe tener al menos 6 caracteres.",
      password_invalid: "La contraseña no es válida.",
      validation_error: "Completa email y contraseña correctamente.",
      invalid_credentials: "Credenciales incorrectas.",
      email_already_registered: "Este correo ya está registrado.",
      db_unavailable: "No se puede conectar a la base de datos (Postgres).",
      network_error: "No se puede conectar con el backend. Verifica que esté activo.",
      api_error: "Error del servidor."
    };

    return codes.map((code) => dictionary[code] || code);
  };

  const handleAuth = async (mode: "login" | "register") => {
    try {
      setErrors([]);
      if (!email.trim() || !password.trim()) {
        setErrors(["Completa email y contraseña."]);
        return;
      }
      const result =
        mode === "login" ? await login(email, password) : await register(email, password);
      setToken(result.access_token);
      setUserEmail(email);
      localStorage.setItem("fantasy_token", result.access_token);
    } catch (err) {
      setErrors(mapAuthErrors(String(err)));
    }
  };

  return (
    <div className="glass mx-auto mt-16 max-w-md space-y-4 rounded-3xl p-6">
      <h1 className="text-2xl font-semibold">Fantasy Liga 1</h1>
      <p className="text-sm text-muted">Ingresa con tu correo local.</p>
      <input
        value={email}
        onChange={(event) => setEmail(event.target.value)}
        placeholder="email"
        className="w-full rounded-xl border border-white/10 bg-black/30 px-4 py-2 text-sm"
      />
      <input
        type="password"
        value={password}
        onChange={(event) => setPassword(event.target.value)}
        placeholder="password"
        className="w-full rounded-xl border border-white/10 bg-black/30 px-4 py-2 text-sm"
      />
      {errors.length > 0 ? (
        <div className="space-y-1 text-xs text-warning">
          {errors.map((message) => (
            <p key={message}>{message}</p>
          ))}
        </div>
      ) : null}
      <div className="flex gap-2">
        <button
          onClick={() => handleAuth("login")}
          className="flex-1 rounded-xl bg-accent px-4 py-2 text-sm font-semibold text-black"
        >
          Login
        </button>
        <button
          onClick={() => handleAuth("register")}
          className="flex-1 rounded-xl border border-white/20 px-4 py-2 text-sm text-ink"
        >
          Registro
        </button>
      </div>
    </div>
  );
}
