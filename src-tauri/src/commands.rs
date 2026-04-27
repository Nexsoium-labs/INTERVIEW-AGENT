use std::sync::Mutex;

use argon2::Argon2;
use rand::{rngs::OsRng, RngCore};
use tauri::{AppHandle, Manager, State};
use tauri_plugin_shell::{
    process::{CommandChild, CommandEvent},
    ShellExt,
};

const CORS_ORIGINS_JSON: &str =
    r#"["tauri://localhost", "http://localhost:1420", "http://127.0.0.1:1420"]"#;
const VAULT_PASSPHRASE: &str = "zt-ate-device-passphrase-v1";
const VAULT_STORE_NAME: &str = "zt-ate-secrets";

#[derive(Default)]
pub struct BackendProcess {
    child: Mutex<Option<CommandChild>>,
}

struct BackendSecrets {
    gemini_api_key: String,
    jwt_secret_key: String,
    operator_master_secret: String,
}

#[tauri::command]
pub fn generate_secrets() -> Result<(String, String), String> {
    let mut jwt_key = [0_u8; 32];
    let mut operator_secret = [0_u8; 32];
    OsRng.fill_bytes(&mut jwt_key);
    OsRng.fill_bytes(&mut operator_secret);
    Ok((hex::encode(jwt_key), hex::encode(operator_secret)))
}

#[tauri::command]
pub async fn check_first_run(app: AppHandle) -> Result<bool, String> {
    let app_data = app.path().app_data_dir().map_err(|err| err.to_string())?;
    Ok(!app_data.join("vault.hold").exists())
}

fn derive_vault_key(password: &str) -> Result<Vec<u8>, String> {
    let mut key = vec![0_u8; 32];
    Argon2::default()
        .hash_password_into(
            password.as_ref(),
            b"zt-ate-sentinel-node-argon2-salt-v1",
            &mut key,
        )
        .map_err(|err| format!("vault key derivation failed: {err}"))?;
    Ok(key)
}

fn load_vaulted_backend_secrets(app: &AppHandle) -> Result<BackendSecrets, String> {
    let vault_path = app
        .path()
        .app_data_dir()
        .map_err(|err| err.to_string())?
        .join("vault.hold");

    if !vault_path.exists() {
        return Err("secure vault snapshot is missing; first-run setup is required".to_string());
    }

    let vault_key = derive_vault_key(VAULT_PASSPHRASE)?;
    let stronghold = tauri_plugin_stronghold::stronghold::Stronghold::new(&vault_path, vault_key)
        .map_err(|err| format!("failed to open secure vault: {err}"))?;
    let client = stronghold
        .load_client(VAULT_STORE_NAME.as_bytes())
        .map_err(|err| format!("failed to load secure vault client: {err}"))?;

    let read_secret = |key: &str| -> Result<String, String> {
        let bytes = client
            .store()
            .get(key.as_bytes())
            .map_err(|err| format!("failed to read vaulted secret '{key}': {err}"))?
            .ok_or_else(|| format!("vaulted secret '{key}' is missing"))?;

        String::from_utf8(bytes)
            .map_err(|_| format!("vaulted secret '{key}' is not valid UTF-8"))
    };

    Ok(BackendSecrets {
        gemini_api_key: read_secret("gemini_api_key")?,
        jwt_secret_key: read_secret("jwt_secret_key")?,
        operator_master_secret: read_secret("operator_master_secret")?,
    })
}

fn spawn_sidecar_with_secrets(
    app: &AppHandle,
    state: &State<'_, BackendProcess>,
    secrets: BackendSecrets,
    boot_source: &str,
) -> Result<(), String> {
    let mut child_slot = state
        .child
        .lock()
        .map_err(|_| "backend process lock poisoned".to_string())?;

    if child_slot.is_some() {
        eprintln!("[zt-backend-sidecar] spawn skipped; already running ({boot_source})");
        return Ok(());
    }

    let command = app
        .shell()
        .sidecar("binaries/zt-backend-sidecar")
        .map_err(|err| err.to_string())?
        .env("GEMINI_API_KEY", secrets.gemini_api_key)
        .env("JWT_SECRET_KEY", secrets.jwt_secret_key)
        .env("OPERATOR_MASTER_SECRET", secrets.operator_master_secret)
        .env("CORS_ORIGINS", CORS_ORIGINS_JSON)
        .env("ENFORCE_SECRET_SCAN", "false");

    let (mut rx, child) = command.spawn().map_err(|err| err.to_string())?;

    tauri::async_runtime::spawn(async move {
        while let Some(event) = rx.recv().await {
            match event {
                CommandEvent::Stdout(line) => {
                    eprintln!("[zt-backend-sidecar stdout] {}", String::from_utf8_lossy(&line));
                }
                CommandEvent::Stderr(line) => {
                    eprintln!("[zt-backend-sidecar stderr] {}", String::from_utf8_lossy(&line));
                }
                CommandEvent::Terminated(payload) => {
                    eprintln!("[zt-backend-sidecar terminated] {:?}", payload);
                }
                _ => {}
            }
        }
    });

    *child_slot = Some(child);
    eprintln!("[zt-backend-sidecar] spawned successfully ({boot_source}); credentials injected");
    Ok(())
}

#[tauri::command]
pub async fn spawn_backend_sidecar(
    app: AppHandle,
    state: State<'_, BackendProcess>,
    gemini_api_key: String,
    jwt_secret_key: String,
    operator_master_secret: String,
) -> Result<(), String> {
    spawn_sidecar_with_secrets(
        &app,
        &state,
        BackendSecrets {
            gemini_api_key,
            jwt_secret_key,
            operator_master_secret,
        },
        "first-run setup",
    )
}

#[tauri::command]
pub async fn spawn_returning_sidecar(
    app: AppHandle,
    state: State<'_, BackendProcess>,
) -> Result<(), String> {
    let secrets = load_vaulted_backend_secrets(&app)?;
    spawn_sidecar_with_secrets(&app, &state, secrets, "returning-user vault boot")
}
