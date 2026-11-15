from __future__ import annotations

from urllib.parse import urlparse
import discord
from discord.ext import commands

from database import GuildConfig

DEFAULT_STAFF_ROLE_NAMES = {
    "staff team",
    "staff manager",
    "staff in training",
    "moderator in training",
    "moderator",
    "administrator",
    "admin",
    "session host",
    "host",
}

DEFAULT_EA_ROLE_NAMES = {
    "early access",
    "server booster",
}


def is_admin_or_manager(member: discord.abc.User) -> bool:
    if not isinstance(member, discord.Member):
        return False
    perms = member.guild_permissions
    return perms.administrator or perms.manage_guild


def is_staff_member(member: discord.abc.User, cfg: GuildConfig) -> bool:
    if not isinstance(member, discord.Member):
        return False
    perms = member.guild_permissions
    if perms.administrator or perms.manage_guild or perms.manage_messages:
        return True

    member_role_ids = {role.id for role in member.roles}
    if cfg.staff_role_ids:
        return bool(member_role_ids & set(cfg.staff_role_ids))

    member_role_names = {role.name.strip().lower() for role in member.roles}
    return bool(member_role_names & DEFAULT_STAFF_ROLE_NAMES)


def is_ea_eligible(member: discord.abc.User, guild: discord.Guild, cfg: GuildConfig) -> bool:
    if not isinstance(member, discord.Member):
        return False
    if is_staff_member(member, cfg):
        return True

    member_role_ids = {role.id for role in member.roles}

    if guild.premium_subscriber_role and guild.premium_subscriber_role.id in member_role_ids:
        return True
    if cfg.booster_role_id and cfg.booster_role_id in member_role_ids:
        return True
    if cfg.ea_role_ids and (member_role_ids & set(cfg.ea_role_ids)):
        return True

    if not cfg.ea_role_ids and cfg.booster_role_id is None:
        member_role_names = {role.name.strip().lower() for role in member.roles}
        return bool(member_role_names & DEFAULT_EA_ROLE_NAMES)

    return False


def validate_url(raw_url: str | None) -> str | None:
    if not raw_url:
        return None
    cleaned = raw_url.strip().strip("<>")
    if not cleaned or any(ch.isspace() for ch in cleaned):
        return None
    if ")" in cleaned or "]" in cleaned:
        return None
    parsed = urlparse(cleaned)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return cleaned


def resolve_target_channel(
    ctx: commands.Context,
    cfg: GuildConfig,
) -> discord.TextChannel | discord.Thread | discord.abc.Messageable:
    if ctx.guild and cfg.session_channel_id:
        channel = ctx.guild.get_channel(cfg.session_channel_id)
        if isinstance(channel, (discord.TextChannel, discord.Thread)):
            return channel
    return ctx.channel


def format_rules_reference(guild: discord.Guild | None, cfg: GuildConfig) -> str:
    if guild and cfg.rules_channel_id:
        channel = guild.get_channel(cfg.rules_channel_id)
        if channel:
            return channel.mention
    return "the server rules channel"


async def safe_delete_trigger(ctx: commands.Context) -> None:
    if ctx.interaction is not None:
        return
    try:
        await ctx.message.delete()
    except (discord.Forbidden, discord.NotFound, discord.HTTPException):
        pass


async def send_ephemeral_or_temp(
    ctx: commands.Context,
    content: str | None = None,
    *,
    embed: discord.Embed | None = None,
    delete_after: float | None = 6.0,
) -> None:
    if ctx.interaction is not None:
        if ctx.interaction.response.is_done():
            await ctx.followup.send(content=content, embed=embed, ephemeral=True)
        else:
            await ctx.reply(content=content, embed=embed, ephemeral=True)
    else:
        await ctx.send(content=content, embed=embed, delete_after=delete_after)
