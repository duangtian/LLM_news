"""
Discord posting functionality using webhooks and discord.py
"""
import asyncio
import time
from typing import List, Dict, Any, Optional
import requests
from loguru import logger

try:
    import discord
    from discord import Webhook
    DISCORD_PY_AVAILABLE = True
except ImportError:
    DISCORD_PY_AVAILABLE = False

from .formatter import DiscordFormatter


class DiscordWebhookPoster:
    """Posts messages to Discord using webhooks"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.webhook_url = config.get('DISCORD_WEBHOOK_URL')
        self.session = requests.Session()
        self.rate_limit_delay = 1.0  # Seconds between requests
        self.last_request_time = 0
        
        if not self.webhook_url:
            raise ValueError("DISCORD_WEBHOOK_URL not provided")
    
    def post_embeds(self, embeds: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Post embeds to Discord via webhook"""
        
        if not embeds:
            logger.warning("No embeds to post")
            return {'success': False, 'error': 'No embeds provided'}
        
        try:
            # Discord allows max 10 embeds per message
            max_embeds_per_message = 10
            results = []
            
            for i in range(0, len(embeds), max_embeds_per_message):
                batch = embeds[i:i + max_embeds_per_message]
                result = self._post_embed_batch(batch)
                results.append(result)
                
                # Rate limiting
                self._wait_for_rate_limit()
            
            # Aggregate results
            all_success = all(r.get('success', False) for r in results)
            message_ids = [r.get('message_id') for r in results if r.get('message_id')]
            
            if all_success:
                logger.info(f"Successfully posted {len(embeds)} embeds to Discord")
                return {
                    'success': True,
                    'message_ids': message_ids,
                    'embed_count': len(embeds)
                }
            else:
                errors = [r.get('error') for r in results if r.get('error')]
                logger.error(f"Some Discord posts failed: {errors}")
                return {
                    'success': False,
                    'error': f"Partial failure: {errors}",
                    'message_ids': message_ids
                }
            
        except Exception as e:
            logger.error(f"Discord webhook post failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def _post_embed_batch(self, embeds: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Post a batch of embeds"""
        
        payload = {
            'embeds': embeds,
            'username': 'LLM News Bot',
            'avatar_url': 'https://cdn.discordapp.com/attachments/123456789/bot-avatar.png'  # Optional
        }
        
        try:
            self._wait_for_rate_limit()
            
            response = self.session.post(
                self.webhook_url,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 204:
                # Discord webhook success returns 204 No Content
                logger.debug(f"Posted batch of {len(embeds)} embeds successfully")
                return {'success': True}
            elif response.status_code == 429:
                # Rate limited
                retry_after = response.json().get('retry_after', 1)
                logger.warning(f"Discord rate limited, retrying after {retry_after}s")
                time.sleep(retry_after)
                return self._post_embed_batch(embeds)  # Retry
            else:
                error_text = response.text
                logger.error(f"Discord webhook error {response.status_code}: {error_text}")
                return {'success': False, 'error': f"HTTP {response.status_code}: {error_text}"}
                
        except requests.RequestException as e:
            logger.error(f"Network error posting to Discord: {e}")
            return {'success': False, 'error': f"Network error: {e}"}
    
    def _wait_for_rate_limit(self):
        """Implement rate limiting"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - time_since_last
            logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s")
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    def test_connection(self) -> bool:
        """Test webhook connection"""
        try:
            test_payload = {
                'content': 'LLM News Bot connection test',
                'username': 'LLM News Bot Test'
            }
            
            response = self.session.post(
                self.webhook_url,
                json=test_payload,
                timeout=10
            )
            
            if response.status_code == 204:
                logger.info("Discord webhook test successful")
                return True
            else:
                logger.error(f"Discord webhook test failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Discord webhook test error: {e}")
            return False


class DiscordBotPoster:
    """Posts messages to Discord using discord.py bot"""
    
    def __init__(self, config: Dict[str, Any]):
        if not DISCORD_PY_AVAILABLE:
            raise ImportError("discord.py library not available")
        
        self.config = config
        self.bot_token = config.get('DISCORD_BOT_TOKEN')
        self.channel_id = int(config.get('DISCORD_CHANNEL_ID', 0))
        
        if not self.bot_token:
            raise ValueError("DISCORD_BOT_TOKEN not provided")
        if not self.channel_id:
            raise ValueError("DISCORD_CHANNEL_ID not provided")
        
        # Create bot client
        intents = discord.Intents.default()
        intents.message_content = True
        self.client = discord.Client(intents=intents)
        self.is_ready = False
        
        @self.client.event
        async def on_ready():
            logger.info(f"Discord bot logged in as {self.client.user}")
            self.is_ready = True
    
    async def post_embeds_async(self, embeds: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Post embeds using discord.py (async)"""
        
        if not embeds:
            return {'success': False, 'error': 'No embeds provided'}
        
        try:
            # Login if not already connected
            if not self.client.is_ready():
                await self.client.login(self.bot_token)
                await self.client.connect()
                
                # Wait for ready
                timeout = 30
                while not self.is_ready and timeout > 0:
                    await asyncio.sleep(1)
                    timeout -= 1
                
                if not self.is_ready:
                    return {'success': False, 'error': 'Bot connection timeout'}
            
            # Get channel
            channel = self.client.get_channel(self.channel_id)
            if not channel:
                return {'success': False, 'error': f'Channel {self.channel_id} not found'}
            
            # Convert embeds to discord.Embed objects
            discord_embeds = []
            for embed_data in embeds:
                embed = discord.Embed.from_dict(embed_data)
                discord_embeds.append(embed)
            
            # Send embeds (max 10 per message)
            message_ids = []
            max_embeds_per_message = 10
            
            for i in range(0, len(discord_embeds), max_embeds_per_message):
                batch = discord_embeds[i:i + max_embeds_per_message]
                message = await channel.send(embeds=batch)
                message_ids.append(str(message.id))
                
                # Small delay between messages
                if i + max_embeds_per_message < len(discord_embeds):
                    await asyncio.sleep(1)
            
            logger.info(f"Successfully posted {len(embeds)} embeds via Discord bot")
            return {
                'success': True,
                'message_ids': message_ids,
                'embed_count': len(embeds)
            }
            
        except discord.DiscordException as e:
            logger.error(f"Discord bot error: {e}")
            return {'success': False, 'error': f'Discord error: {e}'}
        except Exception as e:
            logger.error(f"Unexpected error in Discord bot: {e}")
            return {'success': False, 'error': f'Unexpected error: {e}'}
        finally:
            if self.client.is_closed():
                await self.client.close()
    
    def post_embeds(self, embeds: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Post embeds using discord.py (sync wrapper)"""
        try:
            # Run in event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(self.post_embeds_async(embeds))
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"Error in Discord bot sync wrapper: {e}")
            return {'success': False, 'error': str(e)}
    
    def test_connection(self) -> bool:
        """Test bot connection"""
        try:
            async def test_async():
                await self.client.login(self.bot_token)
                channel = self.client.get_channel(self.channel_id)
                await self.client.close()
                return channel is not None
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(test_async())
                if result:
                    logger.info("Discord bot test successful")
                else:
                    logger.error("Discord bot test failed: channel not found")
                return result
            finally:
                loop.close()
                
        except Exception as e:
            logger.error(f"Discord bot test error: {e}")
            return False


class DiscordPoster:
    """Main Discord poster that chooses between webhook and bot methods"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.formatter = DiscordFormatter(config)
        dry_run_value = config.get('DRY_RUN', 'false')
        self.dry_run = str(dry_run_value).lower() == 'true'
        
        # Choose posting method
        webhook_url = config.get('DISCORD_WEBHOOK_URL')
        bot_token = config.get('DISCORD_BOT_TOKEN')
        
        if webhook_url:
            self.poster = DiscordWebhookPoster(config)
            self.method = 'webhook'
            logger.info("Using Discord webhook for posting")
        elif bot_token and DISCORD_PY_AVAILABLE:
            self.poster = DiscordBotPoster(config)
            self.method = 'bot'
            logger.info("Using Discord bot for posting")
        else:
            raise ValueError("No Discord posting method available (need WEBHOOK_URL or BOT_TOKEN)")
    
    def post_papers(self, papers_with_summaries: List[tuple]) -> Dict[str, Any]:
        """Post papers to Discord"""
        
        try:
            # Format papers as embeds
            embeds = self.formatter.format_papers_as_embeds(papers_with_summaries)
            
            if self.dry_run:
                logger.info(f"DRY RUN: Would post {len(embeds)} embeds to Discord")
                return {
                    'success': True,
                    'dry_run': True,
                    'embed_count': len(embeds),
                    'embeds_preview': embeds[:1]  # Include first embed for preview
                }
            
            # Post to Discord
            result = self.poster.post_embeds(embeds)
            
            return result
            
        except Exception as e:
            logger.error(f"Error posting papers to Discord: {e}")
            return {'success': False, 'error': str(e)}
    
    def post_error(self, error_message: str) -> Dict[str, Any]:
        """Post error message to Discord"""
        
        try:
            error_embed = self.formatter.format_error_embed(error_message)
            
            if self.dry_run:
                logger.info(f"DRY RUN: Would post error to Discord: {error_message}")
                return {'success': True, 'dry_run': True}
            
            result = self.poster.post_embeds([error_embed])
            return result
            
        except Exception as e:
            logger.error(f"Error posting error to Discord: {e}")
            return {'success': False, 'error': str(e)}
    
    def test_connection(self) -> bool:
        """Test Discord connection"""
        try:
            if self.dry_run:
                logger.info("DRY RUN: Skipping Discord connection test")
                return True
            
            return self.poster.test_connection()
            
        except Exception as e:
            logger.error(f"Discord connection test failed: {e}")
            return False
    
    def post_test_message(self) -> Dict[str, Any]:
        """Post test message to Discord"""
        
        try:
            test_embed = self.formatter.format_test_embed()
            
            if self.dry_run:
                logger.info("DRY RUN: Would post test message to Discord")
                return {'success': True, 'dry_run': True}
            
            result = self.poster.post_embeds([test_embed])
            return result
            
        except Exception as e:
            logger.error(f"Error posting test message: {e}")
            return {'success': False, 'error': str(e)}


def create_discord_poster(config: Dict[str, Any]) -> DiscordPoster:
    """Factory function to create Discord poster"""
    return DiscordPoster(config)