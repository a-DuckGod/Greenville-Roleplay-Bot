from __future__ import annotations

import asyncio
import logging
import os
from dotenv import load_dotenv

load_dotenv()

import discord
from discord import app_commands
from discord.ext import commands

import config
from cogs.session import EarlyAccessLinkView, ReleaseLinkView
from database import Database
import utils

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("kgvrp-bot")

COGS = (
    "cogs.session",
    "cogs.moderation",
    "cogs.config_cog",
    "cogs.general",
)


def get_prefix(bot: GreenvilleBot, message: discord.Message) -> list[str]:
    prefix = config.PREFIX
    if message.guild is not None:
        prefix = bot.db.get_guild_config(message.guild.id).prefix
    return commands.when_mentioned_or(prefix)(bot, message)


class GreenvilleBot(commands.Bot):
    def __init__(self, db_path: str | None = None) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True

        super().__init__(
            command_prefix=get_prefix,
            intents=intents,
            help_command=None,
        )
        self.db = Database(db_path or config.DATABASE_PATH)
        self._health_server: asyncio.AbstractServer | None = None

    async def setup_hook(self) -> None:
        # Register persistent button views so EA and Release buttons keep working across restarts
        self.add_view(EarlyAccessLinkView())
        self.add_view(ReleaseLinkView())

        for ext in COGS:
            try:
                await self.load_extension(ext)
                logger.info("Loaded extension: %s", ext)
            except Exception as exc:
                logger.exception("Failed to load extension %s: %s", ext, exc)

        # Global sync makes slash commands available on every server the bot joins
        try:
            synced = await self.tree.sync()
            logger.info("Synced %d global slash command(s).", len(synced))
        except Exception as exc:
            logger.exception("Failed to sync global slash commands: %s", exc)

        # Optional dev guild sync for instant updates during local testing
        guild_id = int(os.environ.get("GUILD_ID", str(config.GUILD_ID)) or 0)
        if guild_id:
            try:
                guild_obj = discord.Object(id=guild_id)
                self.tree.copy_global_to(guild=guild_obj)
                guild_synced = await self.tree.sync(guild=guild_obj)
                logger.info(
                    "Synced %d slash command(s) to dev guild %s.",
                    len(guild_synced),
                    guild_id,
                )
            except Exception as exc:
                logger.warning("Could not sync to dev guild %s: %s", guild_id, exc)

    async def close(self) -> None:
        if self._health_server is not None:
            self._health_server.close()
            await self._health_server.wait_closed()
        self.db.close()
        await super().close()

    async def on_ready(self) -> None:
        assert self.user is not None
        logger.info("Bot online as %s (ID: %s) in %d guild(s).", self.user, self.user.id, len(self.guilds))
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="Greenville RP | /help",
            )
        )

    async def on_guild_join(self, guild: discord.Guild) -> None:
        logger.info("Joined guild: %s (%s)", guild.name, guild.id)
        cfg = self.db.get_guild_config(guild.id)

        target = guild.system_channel
        if target is None or not target.permissions_for(guild.me).send_messages:
            target = next(
                (
                    ch
                    for ch in guild.text_channels
                    if ch.permissions_for(guild.me).send_messages
                ),
                None,
            )

        if target is not None:
            embed = discord.Embed(
                title="👋 Thanks for adding Greenville Roleplay Bot!",
                description=(
                    "Your server is ready to use `/startup`, `/setup`, `/ea`, `/release`, `/over`, and `/purge`.\n\n"
                    "**Recommended next step:**\n"
                    f"Run **`/config wizard`** (or `{cfg.prefix}config wizard`) to set your Rules Channel, "
                    "Staff roles, Early Access roles, and custom prefix."
                ),
                color=discord.Color.green(),
            )
            try:
                await target.send(embed=embed)
            except discord.HTTPException:
                pass


def register_error_handlers(bot: GreenvilleBot) -> None:
    @bot.event
    async def on_command_error(ctx: commands.Context, error: commands.CommandError) -> None:
        if isinstance(error, commands.CommandNotFound):
            return

        original = getattr(error, "original", error)
        if isinstance(error, commands.NoPrivateMessage):
            await utils.send_ephemeral_or_temp(
                ctx, "❌ This command can only be used inside a server."
            )
        elif isinstance(error, commands.MissingPermissions):
            await utils.send_ephemeral_or_temp(
                ctx, "❌ You don't have the required server permissions for this command."
            )
        elif isinstance(error, commands.BotMissingPermissions):
            missing = ", ".join(error.missing_permissions)
            await utils.send_ephemeral_or_temp(
                ctx, f"❌ I am missing required permissions: `{missing}`."
            )
        elif isinstance(error, commands.MissingRequiredArgument):
            await utils.send_ephemeral_or_temp(
                ctx, f"❌ Missing argument: `{error.param.name}`. Use `/help` for command usage."
            )
        elif isinstance(error, commands.BadArgument):
            await utils.send_ephemeral_or_temp(
                ctx, f"❌ Invalid argument provided: {error}"
            )
        elif isinstance(error, commands.CommandOnCooldown):
            await utils.send_ephemeral_or_temp(
                ctx, f"⏳ Please wait {error.retry_after:.1f}s before using this command again."
            )
        else:
            logger.exception("Unhandled command error in %s: %s", ctx.command, original)
            await utils.send_ephemeral_or_temp(
                ctx, "❌ Something went wrong while running that command."
            )

    @bot.tree.error
    async def on_app_command_error(
        interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        logger.exception("Unhandled app command error: %s", error)
        msg = "❌ Something went wrong while executing that command."
        if isinstance(error, app_commands.MissingPermissions):
            msg = "❌ You don't have permission to use this command."
        elif isinstance(error, app_commands.BotMissingPermissions):
            msg = "❌ I don't have the required permissions to run this command."

        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)


async def start_health_server(port: int) -> asyncio.AbstractServer:
    async def handle_client(
        reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        try:
            await reader.read(1024)
            body = b"OK"
            response = (
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: text/plain\r\n"
                + f"Content-Length: {len(body)}\r\n".encode("ascii")
                + b"Connection: close\r\n\r\n"
                + body
            )
            writer.write(response)
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    server = await asyncio.start_server(handle_client, "0.0.0.0", port)
    logger.info("Healthcheck HTTP server listening on port %d.", port)
    return server


def resolve_token() -> str:
    token = (
        os.environ.get("BOT_TOKEN")
        or os.environ.get("DISCORD_TOKEN")
        or config.TOKEN
        or ""
    ).strip()
    if not token or token == "YOUR_REAL_BOT_TOKEN":
        raise RuntimeError(
            "Bot token not set. Set BOT_TOKEN (or DISCORD_TOKEN) in your environment or .env file."
        )
    return token


async def main() -> None:
    token = resolve_token()
    bot = GreenvilleBot()
    register_error_handlers(bot)

    port_raw = os.environ.get("PORT", "").strip()
    if port_raw.isdigit() and int(port_raw) > 0:
        bot._health_server = await start_health_server(int(port_raw))

    async with bot:
        await bot.start(token)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass