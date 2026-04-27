"use client";

import { Maximize2, Minus, X } from "lucide-react";

async function minimize() {
  try {
    const { getCurrentWindow } = await import("@tauri-apps/api/window");
    await getCurrentWindow().minimize();
  } catch {
    // Browser fallback.
  }
}

async function maximize() {
  try {
    const { getCurrentWindow } = await import("@tauri-apps/api/window");
    const win = getCurrentWindow();
    if (await win.isMaximized()) {
      await win.unmaximize();
    } else {
      await win.maximize();
    }
  } catch {
    // Browser fallback.
  }
}

async function close() {
  try {
    const { getCurrentWindow } = await import("@tauri-apps/api/window");
    await getCurrentWindow().close();
  } catch {
    // Browser fallback.
  }
}

export function TitleBar() {
  return (
    <div
      className="h-8 w-full flex items-center justify-between bg-[#050505] border-b border-slate-900 px-3 shrink-0 select-none"
      data-tauri-drag-region
    >
      <div className="flex items-center gap-2 pointer-events-none" data-tauri-drag-region>
        <span className="text-xs text-slate-600 tracking-widest uppercase">
          ZT-ATE Sentinel Node
        </span>
      </div>
      <div className="flex items-center gap-0.5">
        {[
          { icon: Minus, action: minimize, label: "Minimize", hover: "hover:bg-slate-800" },
          { icon: Maximize2, action: maximize, label: "Maximize", hover: "hover:bg-slate-800" },
          { icon: X, action: close, label: "Close", hover: "hover:bg-rose-900" }
        ].map(({ icon: Icon, action, label, hover }) => (
          <button
            key={label}
            onClick={action}
            aria-label={label}
            className={`p-1.5 rounded text-slate-500 ${hover} hover:text-slate-200 transition-colors`}
          >
            <Icon className="h-3.5 w-3.5" />
          </button>
        ))}
      </div>
    </div>
  );
}
