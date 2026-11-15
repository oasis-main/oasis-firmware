//! MQTT client for live device monitoring

use rumqttc::{AsyncClient, MqttOptions, QoS};
use std::time::Duration;
use tokio::sync::mpsc;

pub struct MqttClient {
    client: Option<AsyncClient>,
    rx: Option<mpsc::Receiver<MqttMessage>>,
}

#[derive(Debug, Clone)]
pub struct MqttMessage {
    pub topic: String,
    pub payload: String,
    pub timestamp: String,
}

impl MqttClient {
    pub fn new() -> Self {
        Self {
            client: None,
            rx: None,
        }
    }
    
    pub async fn connect(&mut self, broker: &str, port: u16, client_id: &str) -> anyhow::Result<()> {
        let mut options = MqttOptions::new(client_id, broker, port);
        options.set_keep_alive(Duration::from_secs(30));
        
        let (client, mut eventloop) = AsyncClient::new(options, 100);
        
        let (tx, rx) = mpsc::channel(100);
        self.rx = Some(rx);
        
        // Spawn event loop handler
        tokio::spawn(async move {
            loop {
                match eventloop.poll().await {
                    Ok(notification) => {
                        if let rumqttc::Event::Incoming(rumqttc::Packet::Publish(publish)) = notification {
                            let msg = MqttMessage {
                                topic: publish.topic.clone(),
                                payload: String::from_utf8_lossy(&publish.payload).to_string(),
                                timestamp: chrono::Local::now().format("%H:%M:%S").to_string(),
                            };
                            let _ = tx.send(msg).await;
                        }
                    }
                    Err(e) => {
                        tracing::error!("MQTT error: {:?}", e);
                        tokio::time::sleep(Duration::from_secs(5)).await;
                    }
                }
            }
        });
        
        self.client = Some(client);
        Ok(())
    }
    
    pub async fn subscribe(&self, topic: &str) -> anyhow::Result<()> {
        if let Some(ref client) = self.client {
            client.subscribe(topic, QoS::AtLeastOnce).await?;
        }
        Ok(())
    }
    
    pub fn try_recv(&mut self) -> Option<MqttMessage> {
        if let Some(ref mut rx) = self.rx {
            rx.try_recv().ok()
        } else {
            None
        }
    }
}

impl Default for MqttClient {
    fn default() -> Self {
        Self::new()
    }
}
