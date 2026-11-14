//! Oasis Studio - Desktop application for firmware development

mod app;
mod panels;
mod state;
mod mqtt_client;
mod simulation_bridge;

use eframe::egui;

fn main() -> eframe::Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(tracing_subscriber::EnvFilter::from_default_env())
        .init();

    let options = eframe::NativeOptions {
        viewport: egui::ViewportBuilder::default()
            .with_inner_size([1400.0, 900.0])
            .with_min_inner_size([1000.0, 600.0])
            .with_title("Oasis Studio"),
        ..Default::default()
    };

    eframe::run_native(
        "Oasis Studio",
        options,
        Box::new(|cc| Box::new(app::OasisStudio::new(cc))),
    )
}
