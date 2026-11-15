from __future__ import annotations

import discord
from discord.ext import commands

import config as app_config


class GeneralCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.hybrid_command(
        name="help",
        description="Show all Greenville Roleplay Bot commands and setup info.",
    )
    async def help_command(self, ctx: commands.Context) -> None:
        prefix = (
            self.bot.db.get_guild_config(ctx.guild.id).prefix
            if ctx.guild
            else app_config.PREFIX
        )

        embed = discord.Embed(
            title="🚗 Greenville Roleplay Bot — Commands",
            description=(
                f"All commands work as **slash commands** (`/command`) or with this server's prefix (`{prefix}command`).\n"
                "Server admins can run **`/config wizard`** to customize rules channels, roles, pings, and prefix."
            ),
            color=discord.Color.green(),
        )
        embed.add_field(
            name="🎬 Session Commands (Staff)",
            value=(
                f"`/startup [reactions]` (`{prefix}startup`) — Announce session startup\n"
                f"`/setup` (`{prefix}setup`) — Announce you are setting up the session\n"
                f"`/ea <link>` (`{prefix}ea <link>`) — Post Early Access button for Boosters & EA roles\n"
                f"`/release <peacetime> <frp_speeds> <link>` (`{prefix}release ...`) — Release session with join button\n"
                f"`/over` (`{prefix}over`) — Announce that the session has ended"
            ),
            inline=False,
        )
        embed.add_field(
            name="🧹 Moderation (Staff)",
            value=f"`/purge <amount>` (`{prefix}purge <amount>`) — Bulk delete 1–100 recent messages",
            inline=False,
        )
        embed.add_field(
            name="⚙️ Server Configuration (Admins)",
            value=(
                f"`/config wizard` (`{prefix}config wizard`) — Interactive setup panel\n"
                f"`/config view` (`{prefix}config`) — View current server settings\n"
                f"`/config rules`, `/config session_channel`, `/config prefix`, `/config reactions`\n"
                f"`/config add_staff_role`, `/config add_ea_role`, `/config booster_role`\n"
                f"`/config startup_ping`, `/config release_ping`, `/config reset`"
            ),
            inline=False,
        )
        embed.add_field(
            name="ℹ️ Utility",
            value=f"`/invite` — Get the invite link to add this bot to your own server\n`/ping` — Check bot latency",
            inline=False,
        )

        if ctx.interaction is not None:
            await ctx.reply(embed=embed, ephemeral=True)
        else:
            await ctx.reply(embed=embed)

    @commands.hybrid_command(
        name="invite",
        description="Get the invite link to add this bot to your own Discord server.",
    )
    async def invite(self, ctx: commands.Context) -> None:
        if self.bot.user is None:
            await ctx.reply("❌ Bot is still starting up, try again in a moment.", ephemeral=True)
            return

        permissions = discord.Permissions(
            view_channel=True,
            send_messages=True,
            embed_links=True,
            manage_messages=True,
            read_message_history=True,
            add_reactions=True,
            mention_everyone=True,
            use_external_emojis=True,
        )
        url = discord.utils.oauth_url(
            self.bot.user.id,
            permissions=permissions,
            scopes=("bot", "applications.commands"),
        )

        embed = discord.Embed(
            title="➕ Add Greenville Roleplay Bot to Your Server",
            description=(
                f"**[Click here to invite the bot]({url})**\n\n"
                "Once added to your server, run **`/config wizard`** to set your rules channel, "
                "staff roles, and Early Access roles!"
            ),
            color=discord.Color.blurple(),
        )
        view = discord.ui.View()
        view.add_item(discord.ui.Button(label="Invite Bot", url=url, style=discord.ButtonStyle.link))

        if ctx.interaction is not None:
            await ctx.reply(embed=embed, view=view, ephemeral=True)
        else:
            await ctx.reply(embed=embed, view=view)

    @commands.hybrid_command(
        name="ping",
        description="Check if the bot is online and see its latency.",
    )
    async def ping(self, ctx: commands.Context) -> None:
        latency_ms = round(self.bot.latency * 1000)
        msg = f"🏓 Pong! Latency: **{latency_ms}ms** | Serving **{len(self.bot.guilds)}** server(s)."
        if ctx.interaction is not None:
            await ctx.reply(msg, ephemeral=True)
        else:
            await ctx.reply(msg)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(GeneralCog(bot))
