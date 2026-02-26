"use client";

import { useState } from "react";

import { confirmPasswordReset, login, register, requestPasswordReset } from "@/lib/api";
import { useFantasyStore } from "@/lib/store";

type AuthPanelProps = {
  onAuthenticated?: () => void;
};

export default function AuthPanel({ onAuthenticated }: AuthPanelProps = {}) {
  const setToken = useFantasyStore((state) => state.setToken);
  const setUserEmail = useFantasyStore((state) => state.setUserEmail);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<string[]>([]);
  const [resetMode, setResetMode] = useState(false);
  const [resetCode, setResetCode] = useState("");
  const [resetMessage, setResetMessage] = useState<string | null>(null);
  const [resetStep, setResetStep] = useState<"request" | "confirm">("request");
  const allowPasswordReset = process.env.NEXT_PUBLIC_ENABLE_PASSWORD_RESET === "true";

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
      endpoint_not_found: "No se encontró el endpoint de autenticación. Revisa la API.",
      service_unavailable: "Backend no disponible o servicio caído.",
      server_error: "Error interno del servidor.",
      rate_limited: "Demasiados intentos. Espera un momento.",
      reset_code_invalid: "El código no es válido.",
      reset_code_expired: "El código expiró.",
      reset_code_used: "El código ya fue usado.",
      unauthorized: "No autorizado.",
      forbidden: "Acceso denegado.",
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
      if (password.trim().length < 6) {
        setErrors(["La contraseña debe tener al menos 6 caracteres."]);
        return;
      }
      const result =
        mode === "login" ? await login(email, password) : await register(email, password);
      setToken(result.access_token);
      setUserEmail(email);
      localStorage.setItem("fantasy_token", result.access_token);
      localStorage.setItem("fantasy_email", email);
      onAuthenticated?.();
    } catch (err) {
      setErrors(mapAuthErrors(String(err)));
    }
  };

  const handleRequestReset = async () => {
    setErrors([]);
    setResetMessage(null);
    if (!email.trim()) {
      setErrors(["Ingresa tu correo."]);
      return;
    }
    try {
      await requestPasswordReset(email.trim());
      setResetMessage("Código enviado. Revisa tu correo.");
      setResetStep("confirm");
    } catch (err) {
      setErrors(mapAuthErrors(String(err)));
    }
  };

  const handleConfirmReset = async () => {
    setErrors([]);
    setResetMessage(null);
    if (!email.trim() || !resetCode.trim() || !password.trim()) {
      setErrors(["Completa email, código y nueva contraseña."]);
      return;
    }
    if (password.trim().length < 6) {
      setErrors(["La contraseña debe tener al menos 6 caracteres."]);
      return;
    }
    try {
      await confirmPasswordReset(email.trim(), resetCode.trim(), password.trim());
      setResetMessage("Contraseña actualizada. Ya puedes iniciar sesión.");
      setResetMode(false);
      setResetStep("request");
      setResetCode("");
    } catch (err) {
      setErrors(mapAuthErrors(String(err)));
    }
  };

  return (
    <div className="glass mx-auto mt-16 max-w-md space-y-4 rounded-3xl p-6">
      <div className="flex items-center gap-3">
        <img
          src="/favicon.png"
          alt="Fantasy Liga 1"
          className="h-10 w-10 rounded-full border border-white/10 bg-black/30 p-1"
        />
        <div>
          <h1 className="text-2xl font-semibold">Fantasy Liga 1</h1>
          <p className="text-sm text-muted">Ingresa con un email.</p>
        </div>
      </div>
      <input
        value={email}
        onChange={(event) => setEmail(event.target.value)}
        placeholder="email"
        className="w-full rounded-xl border border-white/10 bg-black/30 px-4 py-2 text-sm"
      />
      {!resetMode || resetStep === "confirm" ? (
        <input
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          placeholder={resetMode ? "nueva contraseña" : "password"}
          className="w-full rounded-xl border border-white/10 bg-black/30 px-4 py-2 text-sm"
        />
      ) : null}
      {resetMode && resetStep === "confirm" ? (
        <input
          value={resetCode}
          onChange={(event) => setResetCode(event.target.value)}
          placeholder="código"
          className="w-full rounded-xl border border-white/10 bg-black/30 px-4 py-2 text-sm"
        />
      ) : null}
      {errors.length > 0 ? (
        <div className="space-y-1 text-xs text-warning">
          {errors.map((message) => (
            <p key={message}>{message}</p>
          ))}
        </div>
      ) : null}
      {resetMessage ? <p className="text-xs text-muted">{resetMessage}</p> : null}
      <div className="flex gap-2">
        {resetMode ? (
          <>
            <button
              onClick={resetStep === "request" ? handleRequestReset : handleConfirmReset}
              className="flex-1 rounded-xl bg-accent px-4 py-2 text-sm font-semibold text-black"
            >
              {resetStep === "request" ? "Enviar código" : "Cambiar clave"}
            </button>
            <button
              onClick={() => {
                setResetMode(false);
                setResetStep("request");
                setResetCode("");
                setResetMessage(null);
                setErrors([]);
              }}
              className="flex-1 rounded-xl border border-white/20 px-4 py-2 text-sm text-ink"
            >
              Volver
            </button>
          </>
        ) : (
          <>
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
          </>
        )}
      </div>
      {!resetMode && allowPasswordReset ? (
        <button
          onClick={() => {
            setResetMode(true);
            setResetStep("request");
            setResetMessage(null);
            setErrors([]);
          }}
          className="w-full text-xs text-muted underline"
        >
          Recuperar contraseña
        </button>
      ) : null}
    </div>
  );
}

