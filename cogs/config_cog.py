from __future__ import annotations

from typing import Literal
import discord
from discord import app_commands
from discord.ext import commands

import config as app_config
from database import GuildConfig
import utils


def _format_ping_display(guild: discord.Guild, mode: str) -> str:
    if mode == "everyone":
        return "@everyone"
    if mode == "here":
        return "@here"
    if mode == "none":
        return "None (no ping)"
    if mode.startswith("role:"):
        rid_str = mode.split(":", 1)[1]
        if rid_str.isdigit():
            role = guild.get_role(int(rid_str))
            return role.mention if role else f"Deleted role (`{rid_str}`)"
    return "@everyone"


def build_config_embed(guild: discord.Guild, cfg: GuildConfig) -> discord.Embed:
    rules_val = (
        f"<#{cfg.rules_channel_id}>"
        if cfg.rules_channel_id and guild.get_channel(cfg.rules_channel_id)
        else "Not set"
    )
    session_val = (
        f"<#{cfg.session_channel_id}>"
        if cfg.session_channel_id and guild.get_channel(cfg.session_channel_id)
        else "Current channel (where command is used)"
    )

    staff_roles = [guild.get_role(rid) for rid in cfg.staff_role_ids]
    staff_roles = [r for r in staff_roles if r is not None]
    staff_val = (
        ", ".join(r.mention for r in staff_roles)
        if staff_roles
        else "Default (`Manage Messages` / `Admin` / standard Staff role names)"
    )

    ea_roles = [guild.get_role(rid) for rid in cfg.ea_role_ids]
    ea_roles = [r for r in ea_roles if r is not None]
    ea_val = ", ".join(r.mention for r in ea_roles) if ea_roles else "Not set"

    if cfg.booster_role_id and guild.get_role(cfg.booster_role_id):
        booster_val = f"<@&{cfg.booster_role_id}>"
    elif guild.premium_subscriber_role:
        booster_val = f"Auto-detected ({guild.premium_subscriber_role.mention})"
    else:
        booster_val = "Not set"

    embed = discord.Embed(
        title=f"⚙️ Server Configuration — {guild.name}",
        description="Customize how the Greenville Roleplay Bot works on your server.",
        color=discord.Color.blurple(),
    )
    embed.add_field(name="Command Prefix", value=f"`{cfg.prefix}`", inline=True)
    embed.add_field(name="Required Reactions", value=f"**{cfg.required_reactions}+**", inline=True)
    embed.add_field(name="Rules Channel", value=rules_val, inline=True)
    embed.add_field(name="Session Channel", value=session_val, inline=False)
    embed.add_field(name="Staff / Host Roles", value=staff_val, inline=False)
    embed.add_field(name="Early Access Roles", value=ea_val, inline=True)
    embed.add_field(name="Booster Role", value=booster_val, inline=True)
    embed.add_field(
        name="Pings",
        value=(
            f"**Startup:** {_format_ping_display(guild, cfg.startup_ping)}\n"
            f"**Release:** {_format_ping_display(guild, cfg.release_ping)}"
        ),
        inline=False,
    )
    embed.set_footer(text="Tip: Run /config wizard for interactive setup, or use /config <setting>.")
    return embed


class PrefixReactionsModal(discord.ui.Modal, title="Edit Prefix & Required Reactions"):
    def __init__(self, wizard: ConfigWizardView, cfg: GuildConfig) -> None:
        super().__init__()
        self.wizard = wizard
        self.prefix_input = discord.ui.TextInput(
            label="Command Prefix (1-5 characters)",
            default=cfg.prefix,
            min_length=1,
            max_length=5,
            required=True,
        )
        self.reactions_input = discord.ui.TextInput(
            label="Required Startup Reactions (1-500)",
            default=str(cfg.required_reactions),
            min_length=1,
            max_length=3,
            required=True,
        )
        self.add_item(self.prefix_input)
        self.add_item(self.reactions_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        assert interaction.guild is not None
        prefix = self.prefix_input.value.strip()
        if not prefix or any(ch.isspace() for ch in prefix):
            await interaction.response.send_message(
                "❌ Prefix cannot be empty or contain spaces.", ephemeral=True
            )
            return

        try:
            reactions = int(self.reactions_input.value.strip())
            if reactions < 1 or reactions > 500:
                raise ValueError
        except ValueError:
            await interaction.response.send_message(
                "❌ Required reactions must be a whole number between 1 and 500.",
                ephemeral=True,
            )
            return

        cfg = self.wizard.bot.db.update_guild_config(
            interaction.guild.id,
            prefix=prefix,
            required_reactions=reactions,
        )
        await interaction.response.edit_message(
            embed=build_config_embed(interaction.guild, cfg),
            view=self.wizard,
        )


class BoosterRoleSubView(discord.ui.View):
    def __init__(self, wizard: ConfigWizardView, parent_interaction: discord.Interaction) -> None:
        super().__init__(timeout=180)
        self.wizard = wizard
        self.parent_interaction = parent_interaction

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not utils.is_admin_or_manager(interaction.user):
            await interaction.response.send_message(
                "❌ Only Administrators or Manage Server users can edit configuration.",
                ephemeral=True,
            )
            return False
        return True

    @discord.ui.select(
        cls=discord.ui.RoleSelect,
        placeholder="Select Booster role...",
        min_values=1,
        max_values=1,
    )
    async def select_booster(
        self, interaction: discord.Interaction, select: discord.ui.RoleSelect
    ) -> None:
        assert interaction.guild is not None
        role = select.values[0]
        cfg = self.wizard.bot.db.update_guild_config(
            interaction.guild.id, booster_role_id=role.id
        )
        await interaction.response.edit_message(
            content=f"✅ Booster role set to {role.mention}.", view=None
        )
        try:
            await self.parent_interaction.edit_original_response(
                embed=build_config_embed(interaction.guild, cfg),
                view=self.wizard,
            )
        except discord.HTTPException:
            pass

    @discord.ui.button(label="Auto-Detect Booster Role", style=discord.ButtonStyle.secondary)
    async def clear_booster(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        assert interaction.guild is not None
        cfg = self.wizard.bot.db.update_guild_config(
            interaction.guild.id, booster_role_id=None
        )
        await interaction.response.edit_message(
            content="✅ Booster role reset to Discord auto-detection.", view=None
        )
        try:
            await self.parent_interaction.edit_original_response(
                embed=build_config_embed(interaction.guild, cfg),
                view=self.wizard,
            )
        except discord.HTTPException:
            pass


class PingSettingsSubView(discord.ui.View):
    def __init__(self, wizard: ConfigWizardView, parent_interaction: discord.Interaction) -> None:
        super().__init__(timeout=180)
        self.wizard = wizard
        self.parent_interaction = parent_interaction

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not utils.is_admin_or_manager(interaction.user):
            await interaction.response.send_message(
                "❌ Only Administrators or Manage Server users can edit configuration.",
                ephemeral=True,
            )
            return False
        return True

    @discord.ui.select(
        placeholder="Startup Ping Mode...",
        options=[
            discord.SelectOption(label="Startup: @everyone", value="everyone"),
            discord.SelectOption(label="Startup: @here", value="here"),
            discord.SelectOption(label="Startup: No Ping", value="none"),
        ],
    )
    async def startup_ping_select(
        self, interaction: discord.Interaction, select: discord.ui.Select
    ) -> None:
        assert interaction.guild is not None
        cfg = self.wizard.bot.db.update_guild_config(
            interaction.guild.id, startup_ping=select.values[0]
        )
        await interaction.response.send_message(
            f"✅ Startup ping updated to `{select.values[0]}`.", ephemeral=True
        )
        try:
            await self.parent_interaction.edit_original_response(
                embed=build_config_embed(interaction.guild, cfg),
                view=self.wizard,
            )
        except discord.HTTPException:
            pass

    @discord.ui.select(
        placeholder="Release Ping Mode...",
        options=[
            discord.SelectOption(label="Release: @everyone", value="everyone"),
            discord.SelectOption(label="Release: @here", value="here"),
            discord.SelectOption(label="Release: No Ping", value="none"),
        ],
    )
    async def release_ping_select(
        self, interaction: discord.Interaction, select: discord.ui.Select
    ) -> None:
        assert interaction.guild is not None
        cfg = self.wizard.bot.db.update_guild_config(
            interaction.guild.id, release_ping=select.values[0]
        )
        await interaction.response.send_message(
            f"✅ Release ping updated to `{select.values[0]}`.", ephemeral=True
        )
        try:
            await self.parent_interaction.edit_original_response(
                embed=build_config_embed(interaction.guild, cfg),
                view=self.wizard,
            )
        except discord.HTTPException:
            pass


class ConfigWizardView(discord.ui.View):
    def __init__(self, bot: commands.Bot, author_id: int) -> None:
        super().__init__(timeout=300)
        self.bot = bot
        self.author_id = author_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not utils.is_admin_or_manager(interaction.user):
            await interaction.response.send_message(
                "❌ Only Administrators or users with Manage Server can use this setup wizard.",
                ephemeral=True,
            )
            return False
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "❌ Only the admin who opened this wizard can modify it.",
                ephemeral=True,
            )
            return False
        return True

    @discord.ui.select(
        cls=discord.ui.ChannelSelect,
        channel_types=[discord.ChannelType.text],
        placeholder="1️⃣ Select your Rules Channel...",
        min_values=1,
        max_values=1,
        row=0,
    )
    async def select_rules_channel(
        self, interaction: discord.Interaction, select: discord.ui.ChannelSelect
    ) -> None:
        assert interaction.guild is not None
        channel = select.values[0]
        cfg = self.bot.db.update_guild_config(
            interaction.guild.id, rules_channel_id=channel.id
        )
        await interaction.response.edit_message(
            embed=build_config_embed(interaction.guild, cfg), view=self
        )

    @discord.ui.select(
        cls=discord.ui.ChannelSelect,
        channel_types=[discord.ChannelType.text],
        placeholder="2️⃣ Select Session Announcement Channel (optional)...",
        min_values=1,
        max_values=1,
        row=1,
    )
    async def select_session_channel(
        self, interaction: discord.Interaction, select: discord.ui.ChannelSelect
    ) -> None:
        assert interaction.guild is not None
        channel = select.values[0]
        cfg = self.bot.db.update_guild_config(
            interaction.guild.id, session_channel_id=channel.id
        )
        await interaction.response.edit_message(
            embed=build_config_embed(interaction.guild, cfg), view=self
        )

    @discord.ui.select(
        cls=discord.ui.RoleSelect,
        placeholder="3️⃣ Select Staff / Host Roles...",
        min_values=1,
        max_values=10,
        row=2,
    )
    async def select_staff_roles(
        self, interaction: discord.Interaction, select: discord.ui.RoleSelect
    ) -> None:
        assert interaction.guild is not None
        role_ids = [r.id for r in select.values if not r.is_default()]
        cfg = self.bot.db.update_guild_config(
            interaction.guild.id, staff_role_ids=role_ids
        )
        await interaction.response.edit_message(
            embed=build_config_embed(interaction.guild, cfg), view=self
        )

    @discord.ui.select(
        cls=discord.ui.RoleSelect,
        placeholder="4️⃣ Select Early Access Roles...",
        min_values=1,
        max_values=10,
        row=3,
    )
    async def select_ea_roles(
        self, interaction: discord.Interaction, select: discord.ui.RoleSelect
    ) -> None:
        assert interaction.guild is not None
        role_ids = [r.id for r in select.values if not r.is_default()]
        cfg = self.bot.db.update_guild_config(
            interaction.guild.id, ea_role_ids=role_ids
        )
        await interaction.response.edit_message(
            embed=build_config_embed(interaction.guild, cfg), view=self
        )

    @discord.ui.button(label="Booster Role", style=discord.ButtonStyle.primary, row=4)
    async def booster_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await interaction.response.send_message(
            "Select your Server Booster role (or reset to auto-detect):",
            view=BoosterRoleSubView(self, interaction),
            ephemeral=True,
        )

    @discord.ui.button(label="Prefix & Reactions", style=discord.ButtonStyle.primary, row=4)
    async def modal_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        assert interaction.guild is not None
        cfg = self.bot.db.get_guild_config(interaction.guild.id)
        await interaction.response.send_modal(PrefixReactionsModal(self, cfg))

    @discord.ui.button(label="Pings", style=discord.ButtonStyle.secondary, row=4)
    async def pings_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await interaction.response.send_message(
            "Choose ping modes for Startup and Release (use `/config startup_ping` or `/config release_ping` to ping a specific role):",
            view=PingSettingsSubView(self, interaction),
            ephemeral=True,
        )

    @discord.ui.button(label="Reset", style=discord.ButtonStyle.danger, row=4)
    async def reset_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        assert interaction.guild is not None
        cfg = self.bot.db.reset_guild_config(interaction.guild.id)
        await interaction.response.edit_message(
            embed=build_config_embed(interaction.guild, cfg), view=self
        )


class ConfigCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def _require_admin(self, ctx: commands.Context) -> bool:
        if ctx.guild is None:
            await utils.send_ephemeral_or_temp(
                ctx, "❌ Configuration commands can only be used inside a server."
            )
            return False
        if not utils.is_admin_or_manager(ctx.author):
            await utils.send_ephemeral_or_temp(
                ctx,
                "❌ You need **Administrator** or **Manage Server** permission to configure the bot.",
            )
            return False
        return True

    @commands.hybrid_group(
        name="config",
        fallback="view",
        invoke_without_command=True,
        description="View or configure bot settings for this server.",
    )
    @commands.guild_only()
    async def config_group(self, ctx: commands.Context) -> None:
        if not await self._require_admin(ctx):
            return
        assert ctx.guild is not None
        cfg = self.bot.db.get_guild_config(ctx.guild.id)
        embed = build_config_embed(ctx.guild, cfg)
        if ctx.interaction is not None:
            await ctx.reply(embed=embed, ephemeral=True)
        else:
            await ctx.reply(embed=embed)

    @config_group.command(
        name="wizard",
        description="Open an interactive setup wizard to configure this server.",
    )
    @commands.guild_only()
    async def wizard(self, ctx: commands.Context) -> None:
        if not await self._require_admin(ctx):
            return
        assert ctx.guild is not None
        cfg = self.bot.db.get_guild_config(ctx.guild.id)
        embed = build_config_embed(ctx.guild, cfg)
        view = ConfigWizardView(self.bot, ctx.author.id)
        if ctx.interaction is not None:
            await ctx.reply(embed=embed, view=view, ephemeral=True)
        else:
            await ctx.reply(embed=embed, view=view)

    @config_group.command(
        name="rules",
        description="Set the rules channel mentioned in startup & release embeds (omit to clear).",
    )
    @commands.guild_only()
    @app_commands.describe(channel="Your server's rules channel (leave empty to clear)")
    async def set_rules(
        self, ctx: commands.Context, channel: discord.TextChannel | None = None
    ) -> None:
        if not await self._require_admin(ctx):
            return
        assert ctx.guild is not None
        self.bot.db.update_guild_config(
            ctx.guild.id, rules_channel_id=channel.id if channel else None
        )
        msg = (
            f"✅ Rules channel set to {channel.mention}."
            if channel
            else "✅ Rules channel cleared."
        )
        await utils.send_ephemeral_or_temp(ctx, msg, delete_after=10.0)

    @config_group.command(
        name="session_channel",
        description="Set a dedicated channel for session announcements (omit to post in current channel).",
    )
    @commands.guild_only()
    @app_commands.describe(channel="Channel for session posts (leave empty to use current channel)")
    async def set_session_channel(
        self, ctx: commands.Context, channel: discord.TextChannel | None = None
    ) -> None:
        if not await self._require_admin(ctx):
            return
        assert ctx.guild is not None
        self.bot.db.update_guild_config(
            ctx.guild.id, session_channel_id=channel.id if channel else None
        )
        msg = (
            f"✅ Session announcements will now be posted in {channel.mention}."
            if channel
            else "✅ Session announcements will post in whichever channel the command is run."
        )
        await utils.send_ephemeral_or_temp(ctx, msg, delete_after=10.0)

    @config_group.command(
        name="add_staff_role",
        description="Allow a role to host sessions and run staff commands.",
    )
    @commands.guild_only()
    @app_commands.describe(role="Role to grant staff/host access")
    async def add_staff_role(self, ctx: commands.Context, role: discord.Role) -> None:
        if not await self._require_admin(ctx):
            return
        assert ctx.guild is not None
        if role.is_default():
            await utils.send_ephemeral_or_temp(ctx, "❌ You cannot add `@everyone` as a staff role.")
            return
        cfg = self.bot.db.get_guild_config(ctx.guild.id)
        roles = list(cfg.staff_role_ids)
        if role.id not in roles:
            roles.append(role.id)
            self.bot.db.update_guild_config(ctx.guild.id, staff_role_ids=roles)
        await utils.send_ephemeral_or_temp(
            ctx, f"✅ Added {role.mention} to Staff / Host roles.", delete_after=10.0
        )

    @config_group.command(
        name="remove_staff_role",
        description="Remove a role from the Staff / Host role list.",
    )
    @commands.guild_only()
    @app_commands.describe(role="Role to remove")
    async def remove_staff_role(self, ctx: commands.Context, role: discord.Role) -> None:
        if not await self._require_admin(ctx):
            return
        assert ctx.guild is not None
        cfg = self.bot.db.get_guild_config(ctx.guild.id)
        roles = [rid for rid in cfg.staff_role_ids if rid != role.id]
        self.bot.db.update_guild_config(ctx.guild.id, staff_role_ids=roles)
        await utils.send_ephemeral_or_temp(
            ctx, f"✅ Removed {role.mention} from Staff / Host roles.", delete_after=10.0
        )

    @config_group.command(
        name="clear_staff_roles",
        description="Clear custom Staff roles and revert to default permissions.",
    )
    @commands.guild_only()
    async def clear_staff_roles(self, ctx: commands.Context) -> None:
        if not await self._require_admin(ctx):
            return
        assert ctx.guild is not None
        self.bot.db.update_guild_config(ctx.guild.id, staff_role_ids=[])
        await utils.send_ephemeral_or_temp(
            ctx, "✅ Cleared custom Staff roles.", delete_after=10.0
        )

    @config_group.command(
        name="add_ea_role",
        description="Add a role that gets pinged and allowed to use Early Access.",
    )
    @commands.guild_only()
    @app_commands.describe(role="Early Access role to add")
    async def add_ea_role(self, ctx: commands.Context, role: discord.Role) -> None:
        if not await self._require_admin(ctx):
            return
        assert ctx.guild is not None
        if role.is_default():
            await utils.send_ephemeral_or_temp(ctx, "❌ You cannot add `@everyone` as an Early Access role.")
            return
        cfg = self.bot.db.get_guild_config(ctx.guild.id)
        roles = list(cfg.ea_role_ids)
        if role.id not in roles:
            roles.append(role.id)
            self.bot.db.update_guild_config(ctx.guild.id, ea_role_ids=roles)
        await utils.send_ephemeral_or_temp(
            ctx, f"✅ Added {role.mention} to Early Access roles.", delete_after=10.0
        )

    @config_group.command(
        name="remove_ea_role",
        description="Remove a role from Early Access roles.",
    )
    @commands.guild_only()
    @app_commands.describe(role="Early Access role to remove")
    async def remove_ea_role(self, ctx: commands.Context, role: discord.Role) -> None:
        if not await self._require_admin(ctx):
            return
        assert ctx.guild is not None
        cfg = self.bot.db.get_guild_config(ctx.guild.id)
        roles = [rid for rid in cfg.ea_role_ids if rid != role.id]
        self.bot.db.update_guild_config(ctx.guild.id, ea_role_ids=roles)
        await utils.send_ephemeral_or_temp(
            ctx, f"✅ Removed {role.mention} from Early Access roles.", delete_after=10.0
        )

    @config_group.command(
        name="clear_ea_roles",
        description="Clear all custom Early Access roles.",
    )
    @commands.guild_only()
    async def clear_ea_roles(self, ctx: commands.Context) -> None:
        if not await self._require_admin(ctx):
            return
        assert ctx.guild is not None
        self.bot.db.update_guild_config(ctx.guild.id, ea_role_ids=[])
        await utils.send_ephemeral_or_temp(
            ctx, "✅ Cleared custom Early Access roles.", delete_after=10.0
        )

    @config_group.command(
        name="booster_role",
        description="Set your Server Booster role (omit to auto-detect Discord's native Booster role).",
    )
    @commands.guild_only()
    @app_commands.describe(role="Server Booster role (leave empty for auto-detect)")
    async def set_booster_role(
        self, ctx: commands.Context, role: discord.Role | None = None
    ) -> None:
        if not await self._require_admin(ctx):
            return
        assert ctx.guild is not None
        self.bot.db.update_guild_config(
            ctx.guild.id, booster_role_id=role.id if role else None
        )
        msg = (
            f"✅ Booster role set to {role.mention}."
            if role
            else "✅ Booster role reset to Discord auto-detection."
        )
        await utils.send_ephemeral_or_temp(ctx, msg, delete_after=10.0)

    @config_group.command(
        name="startup_ping",
        description="Configure who gets pinged on /startup.",
    )
    @commands.guild_only()
    @app_commands.describe(
        mode="Who to ping: everyone, here, role, or none",
        role="Role to ping when mode is 'role'",
    )
    async def set_startup_ping(
        self,
        ctx: commands.Context,
        mode: Literal["everyone", "here", "role", "none"],
        role: discord.Role | None = None,
    ) -> None:
        if not await self._require_admin(ctx):
            return
        assert ctx.guild is not None
        if mode == "role":
            if role is None:
                await utils.send_ephemeral_or_temp(
                    ctx, "❌ Please specify a `role` when setting mode to `role`."
                )
                return
            value = f"role:{role.id}"
        else:
            value = mode
        self.bot.db.update_guild_config(ctx.guild.id, startup_ping=value)
        await utils.send_ephemeral_or_temp(
            ctx,
            f"✅ Startup ping set to {_format_ping_display(ctx.guild, value)}.",
            delete_after=10.0,
        )

    @config_group.command(
        name="release_ping",
        description="Configure who gets pinged on /release.",
    )
    @commands.guild_only()
    @app_commands.describe(
        mode="Who to ping: everyone, here, role, or none",
        role="Role to ping when mode is 'role'",
    )
    async def set_release_ping(
        self,
        ctx: commands.Context,
        mode: Literal["everyone", "here", "role", "none"],
        role: discord.Role | None = None,
    ) -> None:
        if not await self._require_admin(ctx):
            return
        assert ctx.guild is not None
        if mode == "role":
            if role is None:
                await utils.send_ephemeral_or_temp(
                    ctx, "❌ Please specify a `role` when setting mode to `role`."
                )
                return
            value = f"role:{role.id}"
        else:
            value = mode
        self.bot.db.update_guild_config(ctx.guild.id, release_ping=value)
        await utils.send_ephemeral_or_temp(
            ctx,
            f"✅ Release ping set to {_format_ping_display(ctx.guild, value)}.",
            delete_after=10.0,
        )

    @config_group.command(
        name="reactions",
        description="Set the default required reaction count for /startup.",
    )
    @commands.guild_only()
    @app_commands.describe(count="Default reactions needed (1-500)")
    async def set_reactions(self, ctx: commands.Context, count: int) -> None:
        if not await self._require_admin(ctx):
            return
        assert ctx.guild is not None
        if count < 1 or count > 500:
            await utils.send_ephemeral_or_temp(
                ctx, "❌ Reaction count must be between 1 and 500."
            )
            return
        self.bot.db.update_guild_config(ctx.guild.id, required_reactions=count)
        await utils.send_ephemeral_or_temp(
            ctx, f"✅ Default startup reactions set to **{count}+**.", delete_after=10.0
        )

    @config_group.command(
        name="prefix",
        description="Change the text command prefix for this server.",
    )
    @commands.guild_only()
    @app_commands.describe(prefix="New prefix (1-5 characters, no spaces)")
    async def set_prefix(self, ctx: commands.Context, prefix: str) -> None:
        if not await self._require_admin(ctx):
            return
        assert ctx.guild is not None
        cleaned = prefix.strip()
        if not cleaned or len(cleaned) > 5 or any(ch.isspace() for ch in cleaned):
            await utils.send_ephemeral_or_temp(
                ctx, "❌ Prefix must be 1-5 characters with no spaces."
            )
            return
        self.bot.db.update_guild_config(ctx.guild.id, prefix=cleaned)
        await utils.send_ephemeral_or_temp(
            ctx, f"✅ Server command prefix changed to `{cleaned}`.", delete_after=10.0
        )

    @config_group.command(
        name="reset",
        description="Reset all bot configuration on this server to defaults.",
    )
    @commands.guild_only()
    async def reset_config(self, ctx: commands.Context) -> None:
        if not await self._require_admin(ctx):
            return
        assert ctx.guild is not None
        self.bot.db.reset_guild_config(ctx.guild.id)
        await utils.send_ephemeral_or_temp(
            ctx,
            f"✅ Server configuration reset to defaults (prefix: `{app_config.PREFIX}`).",
            delete_after=10.0,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ConfigCog(bot))
