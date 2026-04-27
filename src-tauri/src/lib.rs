mod commands;

use argon2::Argon2;

pub fn run() {
    tauri::Builder::default()
        .manage(commands::BackendProcess::default())
        .plugin(tauri_plugin_process::init())
        .plugin(tauri_plugin_shell::init())
        .plugin(
            tauri_plugin_stronghold::Builder::new(|password| {
                let mut key = vec![0_u8; 32];
                Argon2::default()
                    .hash_password_into(
                        password.as_ref(),
                        b"zt-ate-sentinel-node-argon2-salt-v1",
                        &mut key,
                    )
                    .expect("Argon2 key derivation failed");
                key
            })
            .build(),
        )
        .plugin(tauri_plugin_updater::Builder::new().build())
        .invoke_handler(tauri::generate_handler![
            commands::generate_secrets,
            commands::check_first_run,
            commands::spawn_backend_sidecar,
            commands::spawn_returning_sidecar
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
