declare module "@tauri-apps/plugin-updater" {
  export type DownloadEvent =
    | {
        event: "Started";
        data: {
          contentLength?: number;
        };
      }
    | {
        event: "Progress";
        data: {
          chunkLength: number;
        };
      }
    | {
        event: "Finished";
        data: Record<string, never>;
      };

  export interface Update {
    version: string;
    date?: string;
    body?: string;
    downloadAndInstall(
      onEvent?: (event: DownloadEvent) => void
    ): Promise<void>;
  }

  export function check(): Promise<Update | null>;
}

declare module "@tauri-apps/plugin-process" {
  export function relaunch(): Promise<void>;
}
