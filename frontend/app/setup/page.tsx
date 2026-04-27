"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { CheckCircle2, Key, Loader2, Shield } from "lucide-react";

import { isTauri } from "@/lib/platform";

const VAULT_PASSPHRASE = "zt-ate-device-passphrase-v1";
const STORE_NAME = "zt-ate-secrets";

function encodeSecret(value: string): number[] {
  return Array.from(new TextEncoder().encode(value));
}

async function loadVaultClient() {
  const { appDataDir } = await import("@tauri-apps/api/path");
  const { Stronghold } = await import("@tauri-apps/plugin-stronghold");

  const vaultPath = `${await appDataDir()}/vault.hold`;
  const stronghold = await Stronghold.load(vaultPath, VAULT_PASSPHRASE);
  const client = await stronghold
    .loadClient(STORE_NAME)
    .catch(() => stronghold.createClient(STORE_NAME));

  return { stronghold, client };
}

export default function SetupPage() {
  const router = useRouter();
  const [geminiKey, setGeminiKey] = useState("");
  const [status, setStatus] = useState<"idle" | "provisioning" | "done" | "error">(
    "idle"
  );
  const [errMsg, setErrMsg] = useState("");

  if (!isTauri()) {
    return (
      <div className="h-screen w-full flex items-center justify-center bg-[#0a0a0a]">
        <div className="max-w-sm text-center space-y-4 px-6">
          <Shield className="h-10 w-10 text-slate-500 mx-auto" />
          <h2 className="text-lg font-semibold text-white">Desktop Only</h2>
          <p className="text-sm text-slate-400">
            First-run provisioning is only available in the Sentinel Node
            desktop application.
          </p>
        </div>
      </div>
    );
  }

  async function handleProvision() {
    if (!geminiKey.trim()) {
      setErrMsg("GEMINI_API_KEY is required.");
      return;
    }

    setStatus("provisioning");
    setErrMsg("");

    try {
      const { invoke } = await import("@tauri-apps/api/core");
      const [jwtKey, opSecret] = await invoke<[string, string]>("generate_secrets");
      const { stronghold, client } = await loadVaultClient();
      const store = client.getStore();

      await store.insert("gemini_api_key", encodeSecret(geminiKey.trim()));
      await store.insert("jwt_secret_key", encodeSecret(jwtKey));
      await store.insert("operator_master_secret", encodeSecret(opSecret));
      await stronghold.save();

      await invoke("spawn_backend_sidecar", {
        geminiApiKey: geminiKey.trim(),
        jwtSecretKey: jwtKey,
        operatorMasterSecret: opSecret
      });

      setStatus("done");
      setTimeout(() => router.push("/"), 1_500);
    } catch (err: unknown) {
      setErrMsg(
        `Provisioning failed: ${err instanceof Error ? err.message : String(err)}`
      );
      setStatus("error");
    }
  }

  return (
    <div className="h-screen w-full flex items-center justify-center bg-[#0a0a0a]">
      <div className="w-full max-w-md px-8 py-10 space-y-8">
        <div className="space-y-2 text-center">
          <div className="flex justify-center">
            <div className="rounded-full border border-cyan-400/30 bg-cyan-400/10 p-4">
              <Shield className="h-10 w-10 text-cyan-300" />
            </div>
          </div>
          <h1 className="text-2xl font-semibold text-white">ZT-ATE Sentinel Node</h1>
          <p className="text-xs uppercase tracking-widest text-slate-500">
            First-Run Security Provisioning
          </p>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
          <p className="text-xs text-slate-400 leading-relaxed">
            Enter your Gemini API key. JWT signing secrets and the operator master
            secret are generated locally and stored in the device vault.
          </p>
        </div>

        <div className="space-y-2">
          <label className="block text-xs uppercase tracking-widest text-slate-400">
            Gemini API Key
          </label>
          <div className="relative">
            <Key className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500" />
            <input
              type="password"
              value={geminiKey}
              onChange={(event) => setGeminiKey(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && status === "idle") {
                  handleProvision();
                }
              }}
              placeholder="AIza..."
              disabled={status === "provisioning" || status === "done"}
              className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-slate-700 bg-slate-950 text-slate-100 text-sm placeholder-slate-600 focus:outline-none focus:border-cyan-500 disabled:opacity-50"
            />
          </div>
        </div>

        {errMsg ? <p className="text-sm text-rose-400 text-center">{errMsg}</p> : null}

        <button
          onClick={handleProvision}
          disabled={status === "provisioning" || status === "done" || !geminiKey.trim()}
          className="w-full py-3 rounded-xl bg-cyan-600 hover:bg-cyan-500 disabled:opacity-40 text-white text-sm font-semibold uppercase tracking-widest transition-colors flex items-center justify-center gap-2"
        >
          {status === "provisioning" ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
          {status === "done" ? <CheckCircle2 className="h-4 w-4 text-emerald-300" /> : null}
          {status === "idle" ? "Initialize Sentinel Node" : null}
          {status === "provisioning" ? "Provisioning..." : null}
          {status === "done" ? "Provisioned - Starting..." : null}
          {status === "error" ? "Retry Provisioning" : null}
        </button>
      </div>
    </div>
  );
}
