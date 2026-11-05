#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ChannelItem {
    pub name: String,
    pub stream_url: String,
    pub category: String,
}

#[derive(Debug, Default)]
pub struct IptvPlayer {
    channels: Vec<ChannelItem>,
}

impl IptvPlayer {
    pub fn new() -> Self { Self { channels: Vec::new() } }
    pub fn add_channel(&mut self, name: &str, url: &str, cat: &str) {
        self.channels.push(ChannelItem { name: name.into(), stream_url: url.into(), category: cat.into() });
    }
    pub fn channel_count(&self) -> usize { self.channels.len() }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn test_iptv_player_aaa() {
        // Arrange
        let mut player = IptvPlayer::new();
        // Act
        player.add_channel("News 24", "https://news.stream/live.m3u8", "News");
        // Assert
        assert_eq!(player.channel_count(), 1);
    }
}
