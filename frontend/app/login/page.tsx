"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { ApiError } from "@/lib/api-client";
import { useLogin } from "@/lib/queries/useAuth";
import { Button } from "@/components/ui/Button";
import { Input, Label } from "@/components/ui/Input";

export default function LoginPage() {
  const router = useRouter();
  const login = useLogin();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      await login.mutateAsync({ username, password });
      router.push("/dashboard");
      router.refresh(); // re-runs proxy.ts with the now-present session cookie
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Anmeldung fehlgeschlagen.");
    }
  }

  return (
    <main className="flex flex-1 items-center justify-center px-4">
      <form onSubmit={handleSubmit} className="w-full max-w-sm rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <h1 className="mb-1 text-lg font-semibold">Finanz-Agent</h1>
        <p className="mb-6 text-sm text-slate-500">Persönlicher Finanz-Assistent</p>

        <div className="mb-4">
          <Label htmlFor="username">Benutzername</Label>
          <Input
            id="username"
            autoComplete="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
          />
        </div>

        <div className="mb-4">
          <Label htmlFor="password">Passwort</Label>
          <Input
            id="password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </div>

        {error && <p className="mb-4 text-sm text-red-600">{error}</p>}

        <Button type="submit" className="w-full" disabled={login.isPending}>
          {login.isPending ? "Anmelden…" : "Anmelden"}
        </Button>
      </form>
    </main>
  );
}
