from __future__ import annotations

import random
import discord
from discord import app_commands
from discord.ext import commands

import utils


class EarlyAccessLinkView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Join Early Access",
        style=discord.ButtonStyle.primary,
        custom_id="gvrp:ea_link",
    )
    async def join_early_access(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        if interaction.guild is None or interaction.message is None:
            await interaction.response.send_message(
                "❌ This button can only be used inside a server.", ephemeral=True
            )
            return

        db = getattr(interaction.client, "db", None)
        if db is None:
            await interaction.response.send_message(
                "❌ Bot database is unavailable.", ephemeral=True
            )
            return

        cfg = db.get_guild_config(interaction.guild.id)
        if not utils.is_ea_eligible(interaction.user, interaction.guild, cfg):
            await interaction.response.send_message(
                "❌ You need an Early Access, Server Booster, or Staff role to use this button.",
                ephemeral=True,
            )
            return

        record = db.get_session_link(interaction.message.id)
        if not record or not record.get("url"):
            await interaction.response.send_message(
                "⚠️ This Early Access link has expired or the bot was restarted. Please ask the host to re-post it.",
                ephemeral=True,
            )
            return

        url = record["url"]
        await interaction.response.send_message(
            f"🔗 **[Click here to join Early Access]({url})**",
            ephemeral=True,
        )


class ReleaseLinkView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Join Session",
        style=discord.ButtonStyle.success,
        custom_id="gvrp:release_link",
    )
    async def join_session(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        if interaction.guild is None or interaction.message is None:
            await interaction.response.send_message(
                "❌ This button can only be used inside a server.", ephemeral=True
            )
            return

        db = getattr(interaction.client, "db", None)
        if db is None:
            await interaction.response.send_message(
                "❌ Bot database is unavailable.", ephemeral=True
            )
            return

        record = db.get_session_link(interaction.message.id)
        if not record or not record.get("url"):
            await interaction.response.send_message(
                "⚠️ This session link has expired or the bot was restarted. Please ask the host to re-post it.",
                ephemeral=True,
            )
            return

        url = record["url"]
        await interaction.response.send_message(
            f"🚗 **[Click here to join the session]({url})**",
            ephemeral=True,
        )


class SessionCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def _require_staff(self, ctx: commands.Context):
        if ctx.guild is None:
            await utils.send_ephemeral_or_temp(
                ctx, "❌ This command can only be used inside a server."
            )
            return None

        cfg = self.bot.db.get_guild_config(ctx.guild.id)
        if not utils.is_staff_member(ctx.author, cfg):
            await utils.send_ephemeral_or_temp(
                ctx,
                "❌ You don't have permission to use this command. Ask an admin to assign your Staff role in `/config`.",
            )
            return None
        return cfg

    @commands.hybrid_command(
        name="startup",
        description="Announce that you're hosting a roleplay session.",
    )
    @commands.guild_only()
    @app_commands.describe(reactions="Number of reactions needed (uses server default if omitted)")
    async def startup(
        self, ctx: commands.Context, reactions: int | None = None
    ) -> None:
        cfg = await self._require_staff(ctx)
        if cfg is None:
            return

        reaction_goal = reactions if reactions is not None else cfg.required_reactions
        if reaction_goal < 1 or reaction_goal > 500:
            await utils.send_ephemeral_or_temp(
                ctx, "❌ Required reactions must be between 1 and 500."
            )
            return

        chosen_emoji = random.choice(cfg.startup_emojis)
        rules_ref = utils.format_rules_reference(ctx.guild, cfg)
        ping_text = cfg.format_ping(cfg.startup_ping)

        embed = discord.Embed(
            title="Session Startup!",
            description=(
                f"{ctx.author.mention} is currently hosting a session! "
                f"Please react below if you're going to join the session.\n\n"
                f"Ensure that you have read the rules in {rules_ref} before joining.\n\n"
                f"**{reaction_goal}+ Reactions Needed.**"
            ),
            color=discord.Color.green(),
        )
        embed.set_footer(text=f"Hosted by {ctx.author.display_name}")

        target_channel = utils.resolve_target_channel(ctx, cfg)
        try:
            msg = await target_channel.send(
                content=ping_text,
                embed=embed,
                allowed_mentions=discord.AllowedMentions(everyone=True, roles=True),
            )
        except discord.Forbidden:
            await utils.send_ephemeral_or_temp(
                ctx,
                f"❌ I don't have permission to send messages in {target_channel.mention}.",
            )
            return

        try:
            await msg.add_reaction(chosen_emoji)
        except discord.HTTPException:
            pass

        await utils.safe_delete_trigger(ctx)
        if ctx.interaction is not None:
            await utils.send_ephemeral_or_temp(
                ctx, f"✅ Session startup posted in {target_channel.mention}."
            )

    @commands.hybrid_command(
        name="setup",
        description="Announce that you are currently setting up the session.",
    )
    @commands.guild_only()
    async def setup_session(self, ctx: commands.Context) -> None:
        cfg = await self._require_staff(ctx)
        if cfg is None:
            return

        embed = discord.Embed(
            title="Setting Up",
            description=(
                f"{ctx.author.mention} is currently setting up the session! "
                "This should take around 1 to 2 minutes, so please be patient while the host prepares the server."
            ),
            color=discord.Color.orange(),
        )
        embed.set_footer(text=f"Hosted by {ctx.author.display_name}")

        target_channel = utils.resolve_target_channel(ctx, cfg)
        try:
            await target_channel.send(embed=embed)
        except discord.Forbidden:
            await utils.send_ephemeral_or_temp(
                ctx,
                f"❌ I don't have permission to send messages in {target_channel.mention}.",
            )
            return

        await utils.safe_delete_trigger(ctx)
        if ctx.interaction is not None:
            await utils.send_ephemeral_or_temp(
                ctx, f"✅ Setup announcement posted in {target_channel.mention}."
            )

    @commands.hybrid_command(
        name="ea",
        description="Announce Early Access and share the link with Boosters & Early Access roles.",
    )
    @commands.guild_only()
    @app_commands.describe(link="The private server URL (must start with https:// or http://)")
    async def early_access(
        self, ctx: commands.Context, link: str | None = None
    ) -> None:
        cfg = await self._require_staff(ctx)
        if cfg is None:
            return

        valid_url = utils.validate_url(link)
        if not valid_url:
            await utils.send_ephemeral_or_temp(
                ctx,
                f"❌ Please provide a valid URL starting with `https://` or `http://`.\n"
                f"Usage: `{cfg.prefix}ea <link>`",
            )
            return

        ping_role_ids: list[int] = []
        booster_role = (
            ctx.guild.get_role(cfg.booster_role_id)
            if cfg.booster_role_id
            else ctx.guild.premium_subscriber_role
        )
        if booster_role:
            ping_role_ids.append(booster_role.id)

        for role_id in cfg.ea_role_ids:
            role = ctx.guild.get_role(role_id)
            if role and role.id not in ping_role_ids:
                ping_role_ids.append(role.id)

        ping_text = " ".join(f"<@&{rid}>" for rid in ping_role_ids) if ping_role_ids else None

        embed = discord.Embed(
            title="Early Access",
            description=(
                "Server Boosters and Early Access members may now join the session using the button below!"
            ),
            color=discord.Color.blue(),
        )
        embed.set_footer(text=f"Hosted by {ctx.author.display_name}")

        target_channel = utils.resolve_target_channel(ctx, cfg)
        try:
            msg = await target_channel.send(
                content=ping_text,
                embed=embed,
                view=EarlyAccessLinkView(),
                allowed_mentions=discord.AllowedMentions(roles=True),
            )
        except discord.Forbidden:
            await utils.send_ephemeral_or_temp(
                ctx,
                f"❌ I don't have permission to send messages in {target_channel.mention}.",
            )
            return

        self.bot.db.save_session_link(
            message_id=msg.id,
            guild_id=ctx.guild.id,
            link_type="ea",
            url=valid_url,
            host_id=ctx.author.id,
        )

        await utils.safe_delete_trigger(ctx)
        if ctx.interaction is not None:
            tip = (
                ""
                if ping_role_ids
                else "\n💡 *Tip: Configure Early Access / Booster roles in `/config` so they are pinged automatically.*"
            )
            await utils.send_ephemeral_or_temp(
                ctx, f"✅ Early Access posted in {target_channel.mention}.{tip}"
            )

    @commands.hybrid_command(
        name="release",
        description="Announce session release with Peacetime status, FRP speeds, and join link.",
    )
    @commands.guild_only()
    @app_commands.describe(
        peacetime="Peacetime status (e.g. Normal, Strict, Off)",
        frp_speeds="FRP speed limit (e.g. 75 MPH)",
        link="The private server URL (must start with https:// or http://)",
    )
    async def release(
        self,
        ctx: commands.Context,
        peacetime: str | None = None,
        frp_speeds: str | None = None,
        link: str | None = None,
    ) -> None:
        cfg = await self._require_staff(ctx)
        if cfg is None:
            return

        if not (peacetime and frp_speeds and link):
            await utils.send_ephemeral_or_temp(
                ctx,
                f"❌ Usage: `{cfg.prefix}release <Peacetime> <FRP Speeds> <Link>`",
            )
            return

        valid_url = utils.validate_url(link)
        if not valid_url:
            await utils.send_ephemeral_or_temp(
                ctx,
                "❌ Please provide a valid URL starting with `https://` or `http://`.",
            )
            return

        rules_ref = utils.format_rules_reference(ctx.guild, cfg)
        ping_text = cfg.format_ping(cfg.release_ping)

        embed = discord.Embed(
            title="Session Release",
            description=(
                f"Please read all the rules before joining the session in {rules_ref} "
                "and ensure that you have the correct roles for the vehicles you drive.\n\n"
                f"{ctx.author.mention} has now released the session!\n\n"
                f"**Peacetime Status:** {peacetime}\n"
                f"**FRP Speeds:** {frp_speeds}"
            ),
            color=discord.Color.green(),
        )
        embed.set_footer(text=f"Hosted by {ctx.author.display_name}")

        target_channel = utils.resolve_target_channel(ctx, cfg)
        try:
            msg = await target_channel.send(
                content=ping_text,
                embed=embed,
                view=ReleaseLinkView(),
                allowed_mentions=discord.AllowedMentions(everyone=True, roles=True),
            )
        except discord.Forbidden:
            await utils.send_ephemeral_or_temp(
                ctx,
                f"❌ I don't have permission to send messages in {target_channel.mention}.",
            )
            return

        self.bot.db.save_session_link(
            message_id=msg.id,
            guild_id=ctx.guild.id,
            link_type="release",
            url=valid_url,
            host_id=ctx.author.id,
        )

        await utils.safe_delete_trigger(ctx)
        if ctx.interaction is not None:
            await utils.send_ephemeral_or_temp(
                ctx, f"✅ Session release posted in {target_channel.mention}."
            )

    @release.autocomplete("peacetime")
    async def peacetime_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        options = ["Normal", "Strict", "Off"]
        return [
            app_commands.Choice(name=opt, value=opt)
            for opt in options
            if current.lower() in opt.lower()
        ]

    @release.autocomplete("frp_speeds")
    async def frp_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        options = ["65 MPH", "75 MPH", "80 MPH", "Unlimited"]
        return [
            app_commands.Choice(name=opt, value=opt)
            for opt in options
            if current.lower() in opt.lower()
        ]

    @commands.hybrid_command(
        name="over",
        description="Announce that the current roleplay session has ended.",
    )
    @commands.guild_only()
    async def session_over(self, ctx: commands.Context) -> None:
        cfg = await self._require_staff(ctx)
        if cfg is None:
            return

        embed = discord.Embed(
            title="Session Over",
            description=(
                f"{ctx.author.mention} has ended the session. "
                "Thank you to everyone who attended! Keep an eye out for the next session."
            ),
            color=discord.Color.red(),
        )
        embed.set_footer(text=f"Hosted by {ctx.author.display_name}")

        target_channel = utils.resolve_target_channel(ctx, cfg)
        try:
            await target_channel.send(embed=embed)
        except discord.Forbidden:
            await utils.send_ephemeral_or_temp(
                ctx,
                f"❌ I don't have permission to send messages in {target_channel.mention}.",
            )
            return

        await utils.safe_delete_trigger(ctx)
        if ctx.interaction is not None:
            await utils.send_ephemeral_or_temp(
                ctx, f"✅ Session end posted in {target_channel.mention}."
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(SessionCog(bot))
