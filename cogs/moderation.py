from __future__ import annotations

import datetime
import discord
from discord import app_commands
from discord.ext import commands

import utils


class ModerationCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.hybrid_command(
        name="purge",
        description="Delete recent messages in this channel (skips pinned & messages older than 14 days).",
    )
    @commands.guild_only()
    @app_commands.describe(amount="Number of recent messages to delete (1-100)")
    async def purge(self, ctx: commands.Context, amount: int) -> None:
        if ctx.guild is None:
            await utils.send_ephemeral_or_temp(
                ctx, "❌ This command can only be used inside a server."
            )
            return

        cfg = self.bot.db.get_guild_config(ctx.guild.id)
        if not utils.is_staff_member(ctx.author, cfg):
            await utils.send_ephemeral_or_temp(
                ctx, "❌ You don't have permission to use this command."
            )
            return

        if amount < 1 or amount > 100:
            await utils.send_ephemeral_or_temp(
                ctx, "❌ Please provide a number between 1 and 100."
            )
            return

        me = ctx.guild.me or ctx.guild.get_member(self.bot.user.id)
        if me is None or not ctx.channel.permissions_for(me).manage_messages:
            await utils.send_ephemeral_or_temp(
                ctx, "❌ I need the **Manage Messages** permission in this channel to purge messages."
            )
            return

        if ctx.interaction is not None:
            await ctx.defer(ephemeral=True)
            before_msg = None
        else:
            before_msg = ctx.message
            await utils.safe_delete_trigger(ctx)

        cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=14)
        matched = 0

        def is_valid(msg: discord.Message) -> bool:
            nonlocal matched
            if matched >= amount:
                return False
            if msg.pinned or msg.created_at <= cutoff:
                return False
            matched += 1
            return True

        try:
            deleted = await ctx.channel.purge(
                limit=min(amount + 25, 150),
                check=is_valid,
                before=before_msg,
                reason=f"Purged by {ctx.author}",
            )
        except discord.Forbidden:
            await utils.send_ephemeral_or_temp(
                ctx, "❌ I don't have permission to delete messages in this channel."
            )
            return
        except discord.HTTPException as exc:
            await utils.send_ephemeral_or_temp(
                ctx, f"❌ Failed to purge messages: {exc}"
            )
            return

        await utils.send_ephemeral_or_temp(
            ctx,
            f"✅ Purged **{len(deleted)}** message(s).",
            delete_after=3.0,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ModerationCog(bot))
